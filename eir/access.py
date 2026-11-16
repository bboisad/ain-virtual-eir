"""Who can see what. Every confidentiality rule lives here, so it can be reviewed in one place.

Rules (client kickoff + design doc F11):
1. Founders see and open only the ventures they are members of. Ventures never see each other.
2. AIN staff / mentors see a directory (name, stage, roadmap module, team size, whether help was requested),
   the Mentor Briefs a team explicitly approved for sharing, the Virtual EIR's step judgments (for calibration)
   and, when the team asks for it, the graduation packet. Never the mentor or consultant chats, or the records.
5. The Virtual EIR judges whether a step is complete; AIN staff confirm or reopen the first judgments.
   Only AIN staff approve graduation to NextCorps (all EIRs must agree).
3. IP-sensitive ventures (e.g. lab IP with UR Ventures): the EIR must not collect technical details.
4. Cross-venture lessons are out of scope until they can be de-identified and approved.
6. Consultations are team-only, like the conversation. A consultant sees the lead mentor's brief, a read-only
   overview and the summaries of the files the lead mentor attached, never the mentor chat (no technical details for
   IP-sensitive ventures). The lead mentor receives only the consultation's summary, never its transcript.
7. Project files are team-only. AIN staff never see them (not even their names).
8. Practice sessions are the team's own. AIN staff, consultants and the lead mentor never see them. The lead mentor
   receives a session's feedback only after a member sends it, never the conversation. A practice character sees
   only what its kind allows (character_view): a target customer knows only who they are, never the team's idea.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import consult, overview, practice, roadmap
from .models import Consultation, Member, Rehearsal, StepJudgment, Venture
from .repository import VentureRepository


class Role(str, Enum):
    FOUNDER = "founder"
    STAFF = "staff"


@dataclass(frozen=True)
class Account:
    """A login identity. In production this comes from university sign-in (NetID), not a list."""
    id: str
    name: str
    role: Role = Role.FOUNDER


@dataclass(frozen=True)
class DirectoryEntry:
    """What AIN staff may see about a venture they are not a member of."""
    venture_id: str
    name: str
    stage: str
    team_size: int
    help_requested: bool
    shared_brief_count: int
    module: str = ""  # roadmap position, e.g. "M2 · The Perfect Pitch"
    reviews_pending: int = 0  # Virtual EIR judgments waiting for an EIR check (calibration)
    graduation_requested: bool = False


def all_accounts(known: list[Account], repo: VentureRepository) -> list[Account]:
    """Demo login list: seeded accounts plus founders added to ventures in this session."""
    out = {a.id: a for a in known}
    for v in repo.list():
        for m in v.members:
            if m.account and m.account not in out:
                out[m.account] = Account(m.account, m.name)
    return list(out.values())


def visible_ventures(account: Account, repo: VentureRepository) -> list[Venture]:
    """Ventures whose workspace this account may open."""
    if account.role != Role.FOUNDER:
        return []
    return [v for v in repo.list() if v.member_for_account(account.id)]


def can_open(account: Account, v: Venture) -> bool:
    return account.role == Role.FOUNDER and v.member_for_account(account.id) is not None


def member_in(account: Account, v: Venture) -> Member:
    """The account's member record in a venture; raises if the account has no access."""
    m = v.member_for_account(account.id)
    if m is None or account.role != Role.FOUNDER:
        raise PermissionError(f"{account.id} is not a member of {v.id}")
    return m


def staff_directory(account: Account, repo: VentureRepository) -> list[DirectoryEntry]:
    if account.role != Role.STAFF:
        raise PermissionError("Only AIN staff can see the venture directory")
    return [DirectoryEntry(v.id, v.name, v.stage.value, len(v.members),
                           bool(v.handoff or v.shared_briefs), len(v.shared_briefs),
                           roadmap.info(v.module).name, len(roadmap.pending_reviews(v)),
                           v.graduation == "requested")
            for v in repo.list()]


def shared_briefs_for_staff(account: Account, v: Venture):
    if account.role != Role.STAFF:
        raise PermissionError("Only AIN staff can read shared briefs")
    return list(v.shared_briefs)


def judgments_for_staff(account: Account, v: Venture) -> list[tuple[int, StepJudgment]]:
    """Judgments waiting for an EIR check. They contain verdicts and reasons, never conversation text."""
    if account.role != Role.STAFF:
        raise PermissionError("Only AIN staff can review the Virtual EIR's judgments")
    return roadmap.pending_reviews(v)


def review_judgment(account: Account, v: Venture, index: int, confirm: bool, note: str = "") -> StepJudgment:
    if account.role != Role.STAFF:
        raise PermissionError("Only an AIN EIR or staff member can check a judgment")
    return roadmap.apply_review(v, index, confirm, account.name, note)


def graduation_packet(account: Account, v: Venture) -> str:
    """Asking for the graduation review is the team's consent to share its answers with AIN EIRs."""
    if account.role != Role.STAFF or v.graduation != "requested":
        raise PermissionError("Only AIN staff can read a requested graduation review")
    return roadmap.review_packet(v)


def decide_graduation(account: Account, v: Venture, approve: bool, note: str = "") -> None:
    if account.role != Role.STAFF:
        raise PermissionError("Only AIN EIRs decide graduation")
    roadmap.apply_graduation(v, approve, account.name, note)


# ---- consultations (rule 6) ----
IP_RULE = "IP-SENSITIVE: university-owned IP. Do NOT ask for or repeat technical details of the technology."


def consultant_view(v: Venture, c: Consultation) -> str:
    """What a consultant may see: the lead mentor's brief, a read-only overview and the summaries of the files the lead
    mentor attached; never the mentor chat, never other files."""
    ip = f"\n{IP_RULE}" if v.ip_sensitive else ""
    attached = [f for fid in c.file_ids if (f := v.file(fid)) is not None and f.latest is not None]
    docs = ("\n\nFILES THE MENTOR ATTACHED (summaries; the team's claims, not evidence):\n" + "\n".join(
        f"- \"{f.name}\" (version {f.latest.number}): {f.latest.summary}"
        + (" Claims: " + "; ".join(f.latest.claims) if f.latest.claims else "") for f in attached)) if attached else ""
    return (f"BRIEF FROM THE LEAD MENTOR:\n{c.brief}{ip}\n\n"
            "PROJECT OVERVIEW (read-only; you cannot change records):\n"
            + overview.snapshot_text(v, technical=not v.ip_sensitive) + docs)


def lead_view_of_consultation(c: Consultation) -> str:
    """What the lead mentor receives from a consultation: the fixed-format summary only, never the transcript."""
    name = consult.name_of(c.consultant)
    if c.summary is None:
        return f"The {name} consultation on \"{c.question}\" is still in progress."
    s = c.summary

    def block(title: str, items: list[str]) -> list[str]:
        return [f"{title}:", *(f"- {x}" for x in items)] if items else []

    lines = [f"{name} consultation summary. Question: {s.question}",
             *block("Conclusions", s.conclusions), *block("Evidence still missing", s.missing_evidence),
             *block("Suggested to-dos (you decide)", s.suggested_todos),
             *block("Where the student disagreed", s.disagreements),
             *block("Left for you (outside the consultant's scope)", s.out_of_scope),
             "Needs a human EIR: " + (f"yes ({s.human_topic})" if s.needs_human else "no")]
    if s.student_note:
        lines.append(f"The student's note: {s.student_note}")
    return "\n".join(lines)


# ---- practice sessions (rule 8) ----
def character_view(v: Venture, r: Rehearsal, material: str = "") -> str:
    """What a practice character may see. A target customer: who they are and nothing about the team's idea. A judge:
    the overview and the material the team chose. A challenger: every record, the files' summaries and the chosen
    material. Never a conversation (mentor, consultant or another practice session), never the coach's hints."""
    s = practice.spec(r.character)
    if s.sees == practice.SEGMENT:
        lines = [f"WHO YOU ARE: {r.persona or 'one of the team’s target customers'}"]
        if r.persona_profile:
            lines.append(f"YOUR DETAILS (stay consistent with them): {r.persona_profile}")
        lines += [f"YOUR GROUP, in the team's words: {practice.segment(v)}",
                  "You know nothing about the team's idea, product, prices or plans: only what they tell you here."]
        return "\n".join(lines)
    ip = f"\n{IP_RULE}" if v.ip_sensitive else ""
    parts = ["THE TEAM'S PROJECT (read-only):\n" + overview.snapshot_text(v, technical=not v.ip_sensitive) + ip]
    if s.sees == practice.RECORDS:
        parts.append(practice.records_text(v, technical=not v.ip_sensitive))
    if (h := v.hypothesis(r.assumption_id)) is not None:
        parts.append(f"THE ASSUMPTION TO ATTACK: {h.statement} [{h.rung.label}; {h.status.value}]")
    if material:
        parts.append("MATERIAL THE TEAM CHOSE FOR THIS SESSION (the team's claims, not evidence):\n" + material)
    return "\n\n".join(parts)


def lead_view_of_practice(v: Venture, r: Rehearsal) -> str:
    """What the lead mentor receives from a practice session: the feedback a member sent, never the conversation.
    Practice is not evidence."""
    if not r.shared_at or r.feedback is None:
        raise PermissionError("This practice session's feedback was not sent to the mentor")
    s, f = practice.spec(r.character), r.feedback
    sc = s.scenario(r.scenario)

    def block(title: str, items: list[str]) -> list[str]:
        return [f"{title}:", *(f"- {x}" for x in items)] if items else []

    scores = "; ".join(f"{d.title} {f.scores[d.id]}" for d in s.rubric if d.id in f.scores)
    lines = [f"Practice feedback sent by {v.display_name(r.shared_by)}: {s.name} · {sc.title} · {r.difficulty.value}",
             f"Overall {f.overall:.1f} of 5. {f.verdict}".strip(), f"Scores (1-5): {scores}" if scores else "",
             *block("What worked", f.strengths), *block("Fix these", f.fixes),
             *block("Toughest questions", f.tough_questions), *block("Weak spots found", f.problems),
             *block("To check with real customers (the character's answers are made up)", f.checks),
             *block("Claims the records don't support", f.unsupported_claims),
             f"Hints used: {f.hints_used}" if f.hints_used else "",
             f"The student's note: {r.shared_note}" if r.shared_note else "",
             "This was practice with an AI character: nothing in it is evidence."]
    return "\n".join(line for line in lines if line)
