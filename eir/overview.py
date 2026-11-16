"""Read models for the Overview (the project's homepage) and the Virtual EIR briefing.

The Overview answers three questions: what are we doing, where are we stuck, what do we do next (design v0.19).
- status, focus_card: the current focus with why now, what the records show, what is missing, and the next step
  with one main button. The focus is the Virtual EIR's (or a member's) choice; every other line is a rule.
- steps, current_question: progress on the Foundry roadmap, in words.
- essentials: the snapshot (customer, solution, business model) in the team's words, next to the graded records.
- recent_changes, decisions: what changed, for the activity list and the full history.
- is_new: a project nobody has worked on yet gets a start page instead.

Also builds the Launch Virtual EIR's exit artifact (the one-page preliminary project plan) and the read-only snapshot
a consultant sees. Pure functions of the Venture; the UI formats them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import consult, modes, roadmap
from .models import (CANVAS_BLOCKS, EIR, RUNG_NAMES, ConsultationStatus, Direction, EventKind, Experiment,
                     ExperimentStatus, FocusKind, Hypothesis, Importance, LeadMode, NextStep, Rung, StepJudgment,
                     Venture)

MAX_ACTIONS = 3
MAX_ASSUMPTIONS = 3
MAX_CHANGES = 5
TECHNICAL_BLOCKS = ("Key Resources", "Key Activities")  # withheld from consultants for IP-sensitive ventures


@dataclass(frozen=True)
class Status:
    """Overview block 1. `position` and `progress` depend on the lead mentor."""
    mode: LeadMode
    focus: str
    focus_rung: Rung
    position: str  # Launch: "M2 · Pitch deck · step 23 …"; Optimize: "Bottleneck: Business model"
    progress: str  # "4 of 6 key questions have enough evidence" / "4 of 6 lenses graded"
    deliverable_id: str = ""  # Launch: the deliverable "Check this step" applies to
    judgment: StepJudgment | None = None  # the latest judgment of that deliverable


def _focus(v: Venture) -> tuple[str, Rung]:
    f = v.focus
    if f.kind == FocusKind.ASSUMPTION and (h := v.hypothesis(f.ref)) is not None:
        return f.text or h.statement, h.rung
    if f.kind == FocusKind.QUESTION and (q := roadmap.question(f.ref)) is not None:
        return f.text or q.ask, v.answer(q.id).rung
    if f.kind == FocusKind.CANVAS and f.ref in v.canvas:
        return f.text or f.ref, v.canvas[f.ref].rung
    if f.kind == FocusKind.LENS and f.ref in v.lenses:
        return f.text or f.ref, v.lenses[f.ref].rung
    if f.text:
        return f.text, Rung.NONE
    if v.lead_mode == LeadMode.LAUNCH and (gaps := roadmap.weakest(v, limit=1)):
        q, a = gaps[0]
        return q.ask, a.rung
    return "Tell your Virtual EIR what you are working on", Rung.NONE


def status(v: Venture) -> Status:
    focus, focus_rung = _focus(v)
    if v.lead_mode == LeadMode.OPTIMIZE:
        graded = sum(1 for x in modes.lenses() if x.id in v.lenses)
        b = modes.lens(v.diagnosis.bottleneck)
        return Status(v.lead_mode, focus, focus_rung,
                      f"Bottleneck: {b.title}" if b else "Bottleneck: not found yet",
                      f"{graded} of {len(modes.lenses())} lenses graded")
    d = roadmap.current_deliverable(v)
    if d is None:
        return Status(v.lead_mode, focus, focus_rung, roadmap.position_label(v),
                      "All deliverables of this module are done")
    p = roadmap.progress(v, d)
    return Status(v.lead_mode, focus, focus_rung, roadmap.position_label(v),
                  f"{p.answered} of {p.total} key questions have enough evidence", d.id,
                  roadmap.last_judgment(v, d.id))


def set_by(v: Venture, who: str) -> str:
    """Who set a suggestion, for the Overview: "your Virtual EIR", a member's first name, or "" when unknown."""
    if who == EIR:
        return "your Virtual EIR"
    return v.display_name(who) if who and v.member(who) else ""


def focus_owner(v: Venture) -> str:
    """Who chose the current focus: the Virtual EIR, a member, or the key questions (no focus set yet)."""
    if v.focus.kind == FocusKind.NONE and not v.focus.text:
        return "the key questions"
    return set_by(v, v.focus.set_by) or "your Virtual EIR"


# ---- the focus card: the Overview's main block. Every line comes from the records, by rule (never written by AI) ----
WHY_IMPORTANCE = {Importance.FATAL: 'Rated "fatal if wrong": the project fails if this is not true',
                  Importance.HIGH: "Rated high stakes: a lot depends on it",
                  Importance.MEDIUM: "Rated medium stakes", Importance.LOW: "Rated low stakes"}
MISSING = {Rung.NONE: "No evidence recorded yet",
           Rung.ASSERTION: "No evidence from outside your team yet",
           Rung.SECONDARY: "Nothing from customers yet",
           Rung.SAID: "No one has acted on it yet (signed up, tried, paid)",
           Rung.DID: "No one has paid yet",
           Rung.PAID: "No repeat use yet"}  # the next rung up, whichever way the evidence points; none at rung 6


@dataclass(frozen=True)
class Source:
    """One record behind an evidence label: what it says, its rung, who reported it and when."""
    text: str
    rung: Rung
    source: str = ""  # "Bob · Oct 5", "experiment X-fee"
    date: str = ""
    against: bool = False


@dataclass(frozen=True)
class FocusCard:
    question: str
    why: str  # "" when the records hold no reason (e.g. a free-text focus)
    known: Source | None  # the strongest evidence for it, or the team's answer
    against: Source | None  # the strongest evidence against it (each keeps its own rung)
    missing: str  # "" when nothing is missing
    sources: tuple[Source, ...]  # every record behind it, newest first
    owner: str  # who chose the focus: "your Virtual EIR", a member's first name, or "the key questions"
    next: Experiment | NextStep | None  # the first item of the Action Plan
    cta: str  # the main button: "start" (draft experiment) · "result" (running) · "task" · "chat" (nothing planned)


def _strongest(items: list) -> object | None:
    return max(reversed(items), key=lambda i: int(i.rung), default=None)  # the latest of the strongest


def _cta(item: Experiment | NextStep | None) -> str:
    if isinstance(item, Experiment):
        return "start" if item.status == ExperimentStatus.DRAFT else "result"
    return "task" if item is not None else "chat"


def _focus_question(v: Venture):
    """The key question the focus is about: the one set as focus, else (no focus set) the weakest one."""
    f = v.focus
    if f.kind == FocusKind.QUESTION:
        return roadmap.question(f.ref)
    if f.kind == FocusKind.NONE and not f.text and v.lead_mode == LeadMode.LAUNCH and (gaps := roadmap.weakest(v, 1)):
        return gaps[0][0]
    return None


def focus_card(v: Venture) -> FocusCard:
    """The current focus with why it matters now, what the records already show, what is still missing, and the next
    step with the one main button. The focus itself was chosen by the Virtual EIR (or a member); the rest is rules."""
    s = status(v)
    nxt = next_actions(v, limit=1)
    item = nxt[0] if nxt else None
    why, known, against, sources = "", None, None, ()
    missing = MISSING.get(s.focus_rung, "")
    f = v.focus
    h = v.hypothesis(f.ref) if f.kind == FocusKind.ASSUMPTION else None
    q = None if h is not None else _focus_question(v)
    if h is not None:
        why = WHY_IMPORTANCE.get(h.importance, "")
        sources = tuple(Source(i.text, i.rung, i.source, i.date, i.direction == Direction.AGAINST)
                        for i in reversed(h.evidence_items))
        known = _strongest([x for x in sources if not x.against])
        against = _strongest([x for x in sources if x.against])
    elif q is not None:
        a, d = v.answer(q.id), roadmap.deliverable_of(q.id)
        why = f"Needed to finish {d.short}" if d else ""
        known = Source(a.text, a.rung, a.source) if a.text else None
        missing = f"Needs {RUNG_NAMES[q.need].lower()} (level {int(q.need)})" if a.rung < q.need else ""
        sources = (known,) if known else ()
    elif f.kind == FocusKind.CANVAS and f.ref in v.canvas:
        e = v.canvas[f.ref]
        why = "The weakest evidence on your canvas"
        known = Source(e.text, e.rung, e.source, e.updated) if e.text else None
        sources = (known,) if known else ()
    elif f.kind == FocusKind.LENS and f.ref in v.lenses:
        g = v.lenses[f.ref]
        why = "The weakest of the six lenses"
        known = Source(g.summary, g.rung, "", g.updated) if g.summary else None
        sources = (known,) if known else ()
    return FocusCard(s.focus, why, known, against, missing, sources, focus_owner(v), item, _cta(item))


@dataclass(frozen=True)
class Step:
    """One deliverable on the Foundry roadmap, for the Overview's progress line."""
    id: str
    title: str
    state: str  # "done" · "now" · "later"


def steps(v: Venture) -> list[Step]:
    current = roadmap.current_deliverable(v)
    return [Step(d.id, d.short or d.title, "done" if d.id in v.done else "now" if current and d.id == current.id
                 else "later") for m in roadmap.ORDER for d in roadmap.info(m).deliverables]


def current_question(v: Venture):
    """The key question to answer now: the one the focus card is about (the focus, or the weakest one when no focus is
    set), if it belongs to the current deliverable and still lacks evidence; else the first one without enough
    evidence. None when the step is complete. The focus card and the progress line never name different questions."""
    d = roadmap.current_deliverable(v)
    if d is None:
        return None
    q = _focus_question(v)
    if q is not None and any(x.id == q.id for x in d.questions) and not roadmap.is_met(v, q):
        return q
    return next((x for x in d.questions if not roadmap.is_met(v, x)), None)


def is_new(v: Venture) -> bool:
    """A project nobody has worked on yet: no team message and no records. Its Overview is a start page."""
    if any(v.member(m.author) for m in v.conversation):
        return False
    return not (v.hypotheses or v.experiments or v.next_steps or v.files or v.lenses or v.consultations
                or any(e.text for e in v.canvas.values()) or any(a.text for a in v.answers.values()))


def decisions(v: Venture) -> list:
    """The decisions in the project's timeline, newest first (shown in the full history)."""
    return [e for e in reversed(v.timeline) if e.kind == EventKind.DECISION]


@dataclass(frozen=True)
class CoreItem:
    """One line of the Overview's snapshot: the team's words next to what the records hold."""
    field: str  # the profile field the team edits
    title: str
    text: str  # the team's own words
    record_name: str  # the canvas block (Launch) or lens (Optimize) whose evidence is shown
    record_text: str  # what the records say there (written by the Virtual EIR or the team on the canvas)
    rung: Rung  # graded by the Virtual EIR, never by the team
    why: str
    source: str = ""  # who / when the record was written


CORE = (("customer", "Target customer", "Customer Segments", "customer"),
        ("solution", "Product or solution", "Value Propositions", "solution"),
        ("revenue", "Business model", "Revenue Streams", "business_model"))


def essentials(v: Venture) -> list[CoreItem]:
    """The snapshot's three lines. The text is the team's (profile); the evidence comes from the canvas (Launch) or the
    lenses (Optimize, when graded), so the team's words and the Virtual EIR's grade never mix. When the team has not
    written a line, the record's text is offered as a draft for the team to adopt (the UI says who wrote it)."""
    items = []
    for field, title, block, lens_id in CORE:
        grade = v.lenses.get(lens_id) if v.lead_mode == LeadMode.OPTIMIZE else None
        if grade is not None:
            x = modes.lens(lens_id)
            items.append(CoreItem(field, title, getattr(v.profile, field), f"{x.title if x else lens_id} lens",
                                  grade.summary, grade.rung, grade.why, grade.updated))
            continue
        entry = v.canvas.get(block)
        items.append(CoreItem(field, title, getattr(v.profile, field), block, entry.text if entry else "",
                              entry.rung if entry else Rung.NONE, entry.why if entry else "",
                              entry.source if entry else ""))
    return items


def next_actions(v: Venture, limit: int = MAX_ACTIONS) -> list[Experiment | NextStep]:
    """Experiments first (the one on the focus, running before drafts), then tasks by due date.
    A task that belongs to an experiment is shown through its experiment."""
    focus = v.focus.ref if v.focus.kind == FocusKind.ASSUMPTION else ""
    experiments = sorted((x for x in v.experiments if x.is_open),
                         key=lambda x: (x.assumption_id != focus, x.status != ExperimentStatus.RUNNING,
                                        x.deadline or "9999-12-31"))
    tasks = sorted((s for s in v.open_steps() if not (s.experiment_id and v.experiment(s.experiment_id))),
                   key=lambda s: s.due_date or "9999-12-31")
    return [*experiments, *tasks][:limit]


def key_assumptions(v: Venture, limit: int = MAX_ASSUMPTIONS) -> list[Hypothesis]:
    """The riskiest assumptions: open ones first, then by importance ("if wrong, does the project fail?"),
    then the weakest evidence."""
    return sorted(v.hypotheses, key=lambda h: (not h.status.is_open, -int(h.importance), int(h.rung)))[:limit]


def next_test(v: Venture, h: Hypothesis) -> Experiment | None:
    return next((x for x in v.experiments if x.assumption_id == h.id and x.is_open), None)


@dataclass(frozen=True)
class RecentChange:
    when: str  # ISO timestamp, or a date label ("Oct 9") for a timeline event
    text: str
    by: str
    group: str = ""  # set for record changes, so the UI can offer Undo


def _day(label: str) -> str:
    """A timeline date label as an ISO date, for ordering: "Oct 9" -> "2026-10-09" (this year, or last year when the
    month is still to come). ISO dates pass through."""
    try:
        d = datetime.strptime(f"{label} {date.today().year}", "%b %d %Y").date()
    except ValueError:
        return label[:10]
    return (d.replace(year=d.year - 1) if d > date.today() else d).isoformat()


def recent_changes(v: Venture, limit: int = MAX_CHANGES, events: bool = False) -> list[RecentChange]:
    """Newest first. Timestamps have one-second precision, so changes made together keep their order of making.
    With `events`, the project's timeline too (milestones, decisions, updates such as a shared file): an event has only
    a date, so it comes after the record changes of the same day."""
    items = [(c.created_at, RecentChange(c.created_at, c.summary or f"{c.kind.value} updated", c.by, c.group))
             for c in v.changes if not c.undone_at]
    if events:  # consultations are on the timeline as well
        items += [(_day(e.date), RecentChange(e.date, e.text, e.by)) for e in v.timeline]
    else:
        items += [(c.ended_at, RecentChange(c.ended_at, f"{consult.name_of(c.consultant)} consultant reviewed: "
                                                        f"{c.question}", c.ended_by))
                  for c in v.consultations if c.status == ConsultationStatus.DONE]
    ordered = sorted(enumerate(items), key=lambda pair: (pair[1][0], pair[0]), reverse=True)
    return [r for _, (_, r) in ordered][:limit]


@dataclass(frozen=True)
class MapEntry:
    name: str
    text: str
    rung: Rung
    why: str = ""


def evidence_map(v: Venture) -> list[MapEntry]:
    """Launch: the 9 canvas blocks. Optimize: the 6 lenses."""
    if v.lead_mode == LeadMode.OPTIMIZE:
        return [MapEntry(x.title, v.lenses[x.id].summary, v.lenses[x.id].rung, v.lenses[x.id].why)
                if x.id in v.lenses else MapEntry(x.title, "", Rung.NONE) for x in modes.lenses()]
    return [MapEntry(b, v.canvas[b].text, v.canvas[b].rung, v.canvas[b].why) for b in CANVAS_BLOCKS]


def _test_line(v: Venture, h: Hypothesis) -> str:
    x = next_test(v, h)
    if x is None:
        return "no test planned yet"
    return (f"{x.method} (supported if {x.supported_if or '?'}; refuted if {x.refuted_if or '?'}; "
            f"{x.status.value.lower()})")


def preliminary_plan(v: Venture, today_iso: str | None = None) -> str:
    """The Launch mentor's exit artifact: a one-page plan the team can take away (markdown)."""
    def said(qid: str, fallback: str = "") -> str:
        return v.answer(qid).text or fallback or "—"

    horizon = (date.fromisoformat(today_iso) if today_iso else date.today()) + timedelta(days=30)
    soon = [s for s in v.open_steps() if not s.due_date or date.fromisoformat(s.due_date) <= horizon]
    lines = [f"# Preliminary project plan: {v.name}",
             "_Built from the team's own statements; every claim carries its evidence level "
             "(1 assertion · 2 desk research · 3 customers said · 4 did · 5 paid · 6 retained)._",
             "## Problem", said("cd_problem", v.profile.problem),
             "## First customer (beachhead)", said("cd_segment", v.canvas["Customer Segments"].text),
             "## Value proposition", v.canvas["Value Propositions"].text or "—",
             "## Business model canvas", "| Block | What the team says | Evidence |", "|---|---|---|"]
    lines += [f"| {e.name} | {e.text or '—'} | {e.rung.label} |" for e in evidence_map(v)]
    lines.append("## The 3 riskiest assumptions")
    lines += [f"{i}. **{h.statement}** — {h.rung.label}, {h.status.value.lower()}. Test: {_test_line(v, h)}"
              for i, h in enumerate(key_assumptions(v), 1)] or ["- None recorded yet"]
    lines.append("## Next 30 days")
    lines += [f"- {x.method} (experiment, {x.status.value.lower()}" + (f", due {x.deadline})" if x.deadline else ")")
              for x in v.experiments if x.is_open]
    lines += [f"- {s.text} ({v.display_name(s.owner)}" + (f", due {s.due_date})" if s.due_date else ")") for s in soon]
    return "\n".join(lines)


def consultation_question(v: Venture, consultant_id: str) -> str:
    """The standard question when the team asks for a consultant from the rail: the current focus, seen from the
    consultant's domain."""
    focus = status(v).focus
    if consult.topic_of(focus) == consultant_id:
        return focus
    return f"{consult.name_of(consultant_id)}: where do you stand, given your current focus ({focus.rstrip('?.')})?"


def consultation_brief(v: Venture, question: str) -> str:
    """The standard brief: used by the scripted mentor, and when the AI mentor wrote none."""
    s = status(v)
    risky = "; ".join(f"{h.id} {h.statement} ({h.rung.label})" for h in key_assumptions(v)) or "none recorded"
    return (f"Question: {question}\nThe team's current focus: {s.focus} ({s.focus_rung.label}).\n"
            f"Riskiest assumptions: {risky}.\n"
            "Help them find the weakest assumption behind the question and the cheapest test that could prove it "
            "wrong.")


def snapshot_text(v: Venture, technical: bool = True) -> str:
    """The read-only overview a consultant sees: no conversation; no technical details when `technical` is False."""
    st = status(v)
    lines = [f"VENTURE: {v.name}: {v.description}", f"Lead mentor: {v.lead_mode.value} · {st.position}",
             f"Current focus: {st.focus} ({st.focus_rung.label})", "Riskiest assumptions:"]
    lines += [f"- {h.statement} [{h.rung.label}; {h.status.value}]" for h in key_assumptions(v)] or ["- none yet"]
    lines.append("Evidence map:")
    for e in evidence_map(v):
        text = "(withheld: IP-sensitive venture)" if not technical and e.name in TECHNICAL_BLOCKS else (e.text or "—")
        lines.append(f"- {e.name} [{e.rung.label}]: {text}")
    return "\n".join(lines)
