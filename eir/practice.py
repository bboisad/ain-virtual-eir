"""Practice with AI characters (design 2026-11-07): rehearse with a target customer, a competition judge or a
challenger before the real conversation.

Rules (the early mentor design, section 5, kept in v0.16):
1. A character is a fictional AI role-play partner, labelled as AI. It never plays a real person.
2. Nothing said in practice is evidence. Characters never change records or judge steps (they get no actions).
3. A practice session is the team's own: the lead mentor, consultants and AIN staff never see it (access rule 8).
   A member may send its feedback, never the conversation, to the lead mentor.
4. What a character knows depends on its kind (access.character_view):
   - "segment": the target customer knows only who they are, never the team's idea;
   - "submission": the judge reads the overview and the material the team chose;
   - "records": the challenger reads every record, the files' summaries and the chosen material.
   IP-sensitive ventures: file summaries only, no technical details.
5. The feedback comes from a separate practice coach, not from the character, and it checks what the team said
   against the records (unsupported_claims).

Character skeletons live in knowledge/practice.json: add a character there, no code changes. Without AI, characters
use prepared lines (demo ventures) or simple rules, and the feedback comes from keyword checks (plain_feedback),
marked as simplified.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from . import files, overview, roadmap
from .clock import timestamp
from .filestore import FileStore
from .models import (CHARACTER, Difficulty, Direction, FileKind, Importance, LeadMode, Message, Module, ProjectFile,
                     Rehearsal, RehearsalFeedback, RehearsalStatus, Rung, Venture)

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
SEGMENT, SUBMISSION, RECORDS = "segment", "submission", "records"  # what a character sees
WORDS_PER_MINUTE = 140  # a calm pitch
MATERIAL_CHARS = 6_000  # how much of each chosen file's text the judge and the challenger read
DECK_WORDS = ("deck", "pitch", "slides", "presentation")
NAMES = ("Maya", "Jordan", "Priya", "Sam", "Diego", "Lena", "Omar", "Grace")  # made-up customers without AI


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    goal: str
    minutes: int
    opening: str  # may use {name}, {persona}, {first}, {assumption}, {venture}
    pitch_seconds: int = 0  # the time limit of a pitch; 0 = no pitch
    needs_assumption: bool = False  # the team picks the assumption the character attacks
    direction: str = ""  # for the AI character: how this scenario goes


@dataclass(frozen=True)
class Dimension:
    """One rubric line of the feedback, scored 1 to 5."""
    id: str
    title: str
    good: str = ""  # said when the session did well on it
    fix: str = ""  # said when it needs work, with how to do it


@dataclass(frozen=True)
class CharacterSpec:
    id: str
    name: str
    initials: str
    color: str
    purpose: str
    sees: str  # SEGMENT | SUBMISSION | RECORDS
    knows: str  # what the team is told the character knows
    scenarios: tuple[Scenario, ...]
    difficulty: tuple[tuple[Difficulty, str], ...]
    tips: tuple[str, ...]
    rubric: tuple[Dimension, ...]
    asks: tuple[str, ...]  # questions the character asks without AI, in order
    never: tuple[str, ...]
    wrap_after: int  # the character wraps up after this many team messages
    wrap_up: str
    behaviour: tuple[str, ...] = ()  # for the AI character: how to play the role

    def scenario(self, scenario_id: str) -> Scenario:
        s = next((x for x in self.scenarios if x.id == scenario_id), None)
        if s is None:
            raise ValueError(f"The {self.name.lower()} has no scenario \"{scenario_id}\"")
        return s

    def how(self, difficulty: Difficulty) -> str:
        return dict(self.difficulty).get(Difficulty(difficulty), "")


def _spec(c: dict) -> CharacterSpec:
    return CharacterSpec(
        id=c["id"], name=c["name"], initials=c["initials"], color=c["color"], purpose=c["purpose"], sees=c["sees"],
        knows=c["knows"],
        scenarios=tuple(Scenario(s["id"], s["title"], s["description"], s["goal"], int(s.get("minutes", 10)),
                                 s["opening"], int(s.get("pitch_seconds", 0)), bool(s.get("needs_assumption")),
                                 s.get("direction", "")) for s in c["scenarios"]),
        difficulty=tuple((Difficulty(k), text) for k, text in c["difficulty"].items()),
        tips=tuple(c.get("tips", [])),
        rubric=tuple(Dimension(d["id"], d["title"], d.get("good", ""), d.get("fix", "")) for d in c["rubric"]),
        asks=tuple(c.get("asks", [])), never=tuple(c.get("never", [])), wrap_after=int(c.get("wrap_after", 8)),
        wrap_up=c.get("wrap_up", "Thank you, that's all for today."), behaviour=tuple(c.get("behaviour", [])))


@lru_cache
def characters() -> tuple[CharacterSpec, ...]:
    data = json.loads((KNOWLEDGE / "practice.json").read_text(encoding="utf-8"))["characters"]
    return tuple(_spec(c) for c in data)


def spec(character_id: str) -> CharacterSpec:
    s = next((c for c in characters() if c.id == character_id), None)
    if s is None:
        raise ValueError(f"Unknown practice character: {character_id}")
    return s


def name_of(character_id: str) -> str:
    return next((c.name for c in characters() if c.id == character_id), character_id)


def scenario_of(r: Rehearsal) -> Scenario:
    return spec(r.character).scenario(r.scenario)


# ---- what the characters know ----
def segment(v: Venture) -> str:
    """Who the target customer is: the beachhead the team named, else its canvas, else its own description."""
    canvas = v.canvas.get("Customer Segments")
    return (v.answer("cd_segment").text or (canvas.text if canvas else "") or v.profile.customer
            or "someone who has the problem this venture works on").strip()


def latest_deck(v: Venture) -> ProjectFile | None:
    """The newest pitch deck the team shared: slides, or a document named like a deck."""
    decks = [f for f in v.files if f.latest is not None and f.kind != FileKind.LINK
             and (f.kind == FileKind.SLIDES or any(w in f.name.lower() for w in DECK_WORDS))]
    return max(decks, key=lambda f: f.latest.at, default=None)


def default_files(v: Venture, character_id: str) -> list[str]:
    """The material chosen for a new session: the latest deck for the judge and the challenger, nothing for a
    customer (they know only who they are)."""
    if spec(character_id).sees == SEGMENT:
        return []
    deck = latest_deck(v)
    return [deck.id] if deck else []


def material(v: Venture, store: FileStore | None, r: Rehearsal) -> str:
    """The files chosen for the session, as the judge or the challenger reads them: summary and claims, and the start
    of the text. Summaries only for IP-sensitive ventures, or when no file store is at hand."""
    if spec(r.character).sees == SEGMENT:
        return ""
    rows = []
    for fid in r.file_ids:
        f = v.file(fid)
        if f is None or f.latest is None:
            continue
        row = f"\"{f.name}\" (version {f.latest.number}): {f.latest.summary or '(no summary)'}"
        if f.latest.claims:
            row += "\nClaims: " + "; ".join(f.latest.claims)
        if store is not None and not v.ip_sensitive and f.kind.readable:
            body = files.text(store, f, f.latest).strip()
            if body:
                row += f"\nText (start):\n{body[:MATERIAL_CHARS]}"
        rows.append(row)
    return "\n\n".join(rows)


def records_text(v: Venture, technical: bool = True) -> str:
    """Every record, as the challenger reads it: key-question answers, assumptions with their evidence, experiments,
    tasks and the project files' summaries. Never a conversation, and no internal ids."""
    answers = [f"- {q.ask} [{a.rung.label}] {a.text}" for qid, a in v.answers.items()
               if a.text and (q := roadmap.question(qid)) is not None]
    assumptions = []
    for h in v.hypotheses:
        ev = "; ".join(f"{i.direction.value}: {i.text} ({i.rung.label})" for i in h.evidence_items) or "none recorded"
        assumptions.append(f"- {h.statement} [importance {h.importance.name.lower()}; {h.rung.label}; "
                           f"{h.status.value}]. Evidence: {ev}")
    experiments = []
    for x in v.experiments:
        target = (h.statement if (h := v.hypothesis(x.assumption_id)) else x.lens) or "—"
        experiments.append(f"- [{x.status.value}] {x.method} (tests: {target}). Supported if {x.supported_if or '?'}; "
                           f"refuted if {x.refuted_if or '?'}." + (f" Result: {x.result}." if x.result else "")
                           + (f" Conclusion: {x.conclusion.value}." if x.conclusion.value else ""))
    tasks = [f"- [{s.status.value}] {s.text}" + (f" Result: {s.result}" if s.result else "") for s in v.next_steps]
    docs = [f"- \"{f.name}\" (version {f.latest.number}): {f.latest.summary or '(no summary)'}"
            + (" Claims: " + "; ".join(f.latest.claims) if f.latest.claims else "")
            for f in v.files if f.latest is not None]
    blocks = [("KEY-QUESTION ANSWERS (the team's words [evidence])", answers),
              ("ASSUMPTIONS [importance; strongest evidence; conclusion]", assumptions),
              ("EXPERIMENTS", experiments), ("TASKS", tasks),
              ("PROJECT FILES (summaries; the team's claims, not evidence)", docs)]
    text = "\n".join(f"{title}:\n" + ("\n".join(rows) or "- none") for title, rows in blocks)
    return text if technical else text.replace("(summaries;", "(summaries only, no technical details;")


# ---- a session ----
def team_messages(r: Rehearsal) -> list[Message]:
    return [m for m in r.messages if m.author != CHARACTER]


def turns(r: Rehearsal) -> int:
    """How many messages the team has sent."""
    return len(team_messages(r))


def first_name(r: Rehearsal) -> str:
    return r.persona.split(",")[0].strip() if r.persona else ""


def character_label(r: Rehearsal) -> str:
    """How the character is named in the chat: a customer by name, the others by role. Always marked as AI."""
    name = first_name(r)
    return f"{name} ({spec(r.character).name.lower()}, AI)" if name else f"{spec(r.character).name} (AI)"


def opening(v: Venture, r: Rehearsal, first: str = "", persona: str = "") -> str:
    """The scenario's opening line, filled in."""
    sc = scenario_of(r)
    persona = persona.strip() or r.persona or "one of your target customers"
    h = v.hypothesis(r.assumption_id)
    return sc.opening.format(name=persona.split(",")[0].strip(), persona=persona, first=first.strip(),
                             assumption=h.statement if h else "", venture=v.name).strip()


def plain_persona(v: Venture, r: Rehearsal) -> tuple[str, str]:
    """A made-up target customer without AI: a first name and the segment. Details come up as they are asked."""
    try:
        name = NAMES[int(r.id.removeprefix("R-"), 16) % len(NAMES)]
    except ValueError:
        name = NAMES[0]
    return (f"{name}, one of your target customers",
            f"{name} belongs to this group: {segment(v)}. Nothing else is fixed yet; keep answers consistent.")


def new(v: Venture, character_id: str, scenario_id: str, difficulty: Difficulty = Difficulty.REALISTIC, *, by: str,
        file_ids: tuple[str, ...] = (), assumption_id: str = "") -> Rehearsal:
    """Check the settings and make a session. It joins the venture once it has its opening (begin)."""
    s = spec(character_id)
    sc = s.scenario(scenario_id)
    difficulty = Difficulty(difficulty)
    if s.sees == SEGMENT:
        file_ids = ()  # a customer knows only who they are
    if any(v.file(fid) is None for fid in file_ids):
        raise ValueError("One of the chosen files no longer exists. Choose the material again.")
    if sc.needs_assumption and v.hypothesis(assumption_id) is None:
        raise ValueError("Choose the assumption the challenger should attack")
    return Rehearsal(character=s.id, scenario=sc.id, difficulty=difficulty, file_ids=list(dict.fromkeys(file_ids)),
                     assumption_id=assumption_id if sc.needs_assumption else "", started_by=by)


def begin(v: Venture, r: Rehearsal, opening_line: str, persona: str = "", persona_profile: str = "") -> Rehearsal:
    """Add the session to the venture with the character's opening line."""
    if not opening_line.strip():
        raise ValueError("The character has no opening line")
    r.persona, r.persona_profile = persona.strip(), persona_profile.strip()
    r.messages.append(Message(CHARACTER, opening_line.strip()))
    v.rehearsals.append(r)
    return r


def add_message(r: Rehearsal, author: str, text: str) -> Message:
    if r.status != RehearsalStatus.OPEN:
        raise ValueError("This practice session has ended. Practise again to start a new one.")
    if r.wrapped_up and author != CHARACTER:
        raise ValueError("The character has wrapped up. Get your feedback, or choose Keep going.")
    text = text.strip()
    if not text:
        raise ValueError("Write a message first")
    m = Message(author, text)
    r.messages.append(m)
    return m


def awaiting_reply(r: Rehearsal) -> bool:
    """The latest message is the team's and the character has not answered it (its reply failed)."""
    return r.status == RehearsalStatus.OPEN and bool(r.messages) and r.messages[-1].author != CHARACTER


def keep_going(r: Rehearsal) -> None:
    """The team wants to continue after the character wrapped up."""
    if r.status != RehearsalStatus.OPEN:
        raise ValueError("This practice session has ended")
    r.wrapped_up = False


def add_hint(r: Rehearsal, text: str) -> str:
    """A whisper from the practice coach. The character never sees it; the feedback counts it."""
    if r.status != RehearsalStatus.OPEN:
        raise ValueError("This practice session has ended")
    text = " ".join(text.split())
    if not text:
        raise ValueError("No hint")
    r.hints.append(text)
    return text


def transcript(v: Venture, r: Rehearsal) -> str:
    """The session as text, for the practice coach (never for the lead mentor)."""
    label = character_label(r)
    return "\n".join(f"{label if m.author == CHARACTER else v.display_name(m.author)}: {m.text}" for m in r.messages)


def check_can_finish(r: Rehearsal) -> None:
    if r.status != RehearsalStatus.OPEN:
        raise ValueError("This practice session has already ended")
    if not team_messages(r):
        raise ValueError("Say something first: there is nothing to give feedback on yet.")


def clean_scores(s: CharacterSpec, scores: dict) -> dict[str, int]:
    """Scores for the rubric's dimensions only, each 1 to 5."""
    out = {}
    for d in s.rubric:
        try:
            out[d.id] = max(1, min(5, int(round(float(scores[d.id])))))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def overall(scores: dict[str, int]) -> float:
    return round(sum(scores.values()) / len(scores), 1) if scores else 0.0


def finish(v: Venture, r: Rehearsal, feedback: RehearsalFeedback, *, by: str) -> Rehearsal:
    """End the session with the practice coach's feedback. The team sees it first and decides whether to send it."""
    check_can_finish(r)
    feedback.scores = clean_scores(spec(r.character), feedback.scores)
    feedback.overall = overall(feedback.scores)
    feedback.hints_used = len(r.hints)
    feedback.written_at = feedback.written_at or timestamp()
    r.feedback, r.status, r.ended_at, r.wrapped_up = feedback, RehearsalStatus.DONE, timestamp(), True
    return r


NOTE_LIMIT = 280  # the member's note to the mentor is one line


def share(r: Rehearsal, *, by: str, note: str = "") -> Rehearsal:
    """A member sends the feedback (never the conversation) to the lead mentor, with an optional one-line note."""
    if r.feedback is None:
        raise ValueError("End the session first: only its feedback can be sent to your Virtual EIR")
    if r.shared_at:
        raise ValueError("This feedback was already sent to your Virtual EIR")
    note = " ".join(note.split())
    if len(note) > NOTE_LIMIT:
        raise ValueError(f"Keep your note to one line ({NOTE_LIMIT} characters)")
    r.shared_at, r.shared_by, r.shared_note = timestamp(), by, note
    return r


def shared(v: Venture) -> list[Rehearsal]:
    """Sessions whose feedback a member sent to the lead mentor, oldest first."""
    return [r for r in v.rehearsals if r.shared_at and r.feedback is not None]


# ---- the lead mentor suggests a session: "<character>/<scenario>" or "challenger/assumption/<assumption id>" ----
@dataclass(frozen=True)
class Suggestion:
    character: str
    scenario: str
    assumption_id: str = ""

    def __str__(self) -> str:
        return "/".join(x for x in (self.character, self.scenario, self.assumption_id) if x)

    @property
    def label(self) -> str:
        """The button under the mentor's reply, e.g. "Practise with the competition judge: 3-minute pitch + questions"."""
        s = spec(self.character)
        return f"Practise with the {s.name.lower()}: {s.scenario(self.scenario).title}"


def suggestion(v: Venture, character_id: str, scenario_id: str, assumption_id: str = "") -> Suggestion:
    """Check a suggested session against the characters and the records."""
    sc = spec(character_id).scenario(scenario_id)
    if sc.needs_assumption:
        if v.hypothesis(assumption_id) is None:
            raise ValueError(f"the {scenario_id} scenario needs the id of an existing assumption (assumption_id)")
    else:
        assumption_id = ""
    return Suggestion(character_id, scenario_id, assumption_id)


def parse_suggestion(v: Venture, text: str) -> Suggestion | None:
    """The suggestion saved on a mentor message, if it still fits the characters and the records."""
    parts = (text.split("/") + ["", ""])[:3] if text else []
    try:
        return suggestion(v, *parts) if parts else None
    except ValueError:
        return None


def delete(v: Venture, r: Rehearsal) -> Rehearsal:
    """Remove a practice session. Feedback the mentor already received stays where it was used, so it can't be
    removed."""
    if r.shared_at:
        raise ValueError("This feedback was sent to your Virtual EIR, so the session is kept")
    v.rehearsals = [x for x in v.rehearsals if x.id != r.id]
    return r


def history(v: Venture, character_id: str = "") -> list[Rehearsal]:
    """Practice sessions, newest first."""
    return [r for r in reversed(v.rehearsals) if not character_id or r.character == character_id]


def in_progress(v: Venture) -> list[Rehearsal]:
    return [r for r in history(v) if r.status == RehearsalStatus.OPEN]


def scores_over_time(v: Venture, character_id: str) -> list[float]:
    """The overall scores of the finished sessions with one character, oldest first (progress at a glance)."""
    return [r.feedback.overall for r in v.rehearsals if r.character == character_id and r.feedback is not None]


def minutes(r: Rehearsal) -> int:
    """How long the session took, from the start to its end (or to the latest message)."""
    end = r.ended_at or (r.messages[-1].created_at if r.messages else r.started_at)
    try:
        seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(r.started_at)).total_seconds()
    except ValueError:
        return 0
    return max(1, round(seconds / 60))


# ---- pitch timing: a pitch is typed or pasted, its length estimated from the words ----
def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass(frozen=True)
class Timing:
    words: int
    seconds: int
    target: int = 0  # seconds; 0 = no limit

    @property
    def over(self) -> bool:
        return bool(self.target) and self.seconds > self.target

    @property
    def label(self) -> str:
        text = f"{self.words} words ≈ {clock(self.seconds)}"
        return text + (f" (target {clock(self.target)})" if self.target else "")


def estimate(text: str, target: int = 0) -> Timing:
    words = len(text.split())
    return Timing(words, round(words * 60 / WORDS_PER_MINUTE), target)


def pitch_timing(r: Rehearsal) -> Timing | None:
    """In a pitch scenario the team's first message is the pitch."""
    sc, team = scenario_of(r), team_messages(r)
    if not sc.pitch_seconds or not team:
        return None
    return estimate(team[0].text, sc.pitch_seconds)


# ---- "Recommended now" ----
@dataclass(frozen=True)
class Recommendation:
    character: str
    scenario: str
    difficulty: Difficulty
    file_ids: tuple[str, ...]
    reason: str


def recommended(v: Venture) -> Recommendation:
    """The practice that fits where the venture is: interviews in Module 1, a judge on the pitch deck step, otherwise
    a challenger."""
    if v.lead_mode == LeadMode.LAUNCH:
        d = roadmap.current_deliverable(v)
        if v.module == Module.M1:
            if d is not None and d.id == "bmc":
                return Recommendation("customer", "solution", Difficulty.REALISTIC, (),
                                      "You're working on the business model: show your idea to a customer and listen "
                                      "for objections.")
            return Recommendation("customer", "discovery", Difficulty.REALISTIC, (),
                                  "You're on customer discovery: rehearse an interview before the real ones.")
        if d is not None and d.id == "pitch_deck":
            return Recommendation("judge", "pitch", Difficulty.REALISTIC, tuple(default_files(v, "judge")),
                                  "You're on the pitch deck step: pitch to a competition judge.")
    return Recommendation("challenger", "holes", Difficulty.REALISTIC, tuple(default_files(v, "challenger")),
                          "Let a challenger find the weak spots in your project before an investor does.")


# ---- checks against the records (for the feedback; they never change a record) ----
NUMBER = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")
YEAR = re.compile(r"^(?:19|20)\d\d$")
PAYMENT = re.compile(r"\b(?:paid|paying (?:customers|users)|pre-?orders?|pre-?paid|deposits?|signed|letters? of intent|"
                     r"LOIs?|contracts?|revenue)\b", re.I)
NEGATION = re.compile(r"\b(?:no|not|nobody|none|never|yet)\b|n't\b", re.I)
PLAN = re.compile(r"\b(?:will|would|plan(?:s|ned)?|going to|want to|test(?:s|ing)?|try(?:ing)?|offer|count|next|if)\b",
                  re.I)  # a plan or a test is not a claim that customers paid
OUR_PLAN = re.compile(r"\b(?:we(?:'d|'ll| would| will| plan| want| intend| are going)|i(?:'d|'ll| would| will| plan))\b",
                      re.I)  # "we'd buy 300 crates" is the team's plan, not a claim about what happened
DEMO_MARK = "_Scripted demo reply (no AI connected)._"  # ends a character's reply written by simple rules


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _counts(number: str) -> bool:
    """Numbers worth checking: amounts, percentages and counts of 10 or more; not years."""
    core = number.strip("$%").replace(",", "")
    if YEAR.match(core):
        return False
    return "$" in number or "%" in number or len(core.split(".")[0]) >= 2


def _known(v: Venture) -> str:
    p = v.profile
    profile = " ".join([p.self_description, p.one_liner, p.problem, p.customer, p.solution, p.alternatives, p.evidence,
                        p.revenue, p.need])
    return "\n".join([records_text(v), overview.snapshot_text(v), v.description, profile]).lower()


def _mentioned(number: str, known: str) -> bool:
    core = number.strip("$%").replace(",", "").rstrip(".")
    return re.search(rf"(?<![\d.]){re.escape(core)}(?![\d])", known.replace(",", "")) is not None


def payment_recorded(v: Venture) -> bool:
    """A customer paid, pre-ordered or signed, according to the records."""
    items = [i.rung for h in v.hypotheses for i in h.evidence_items if i.direction == Direction.FOR]
    return max([*items, *(a.rung for a in v.answers.values())], default=Rung.NONE) >= Rung.PAID


def quote(sentence: str, limit: int = 140) -> str:
    return f"\"{sentence[:limit].rstrip()}{'…' if len(sentence) > limit else ''}\""


def find_unsupported(v: Venture, texts: list[str]) -> list[tuple[str, str]]:
    """(sentence, why) for what the team said that its records don't support: numbers the records don't contain, and
    payments or signed commitments when none is recorded."""
    known, paid, out = _known(v), payment_recorded(v), []
    for text in texts:
        for s in sentences(text):
            missing = None if OUR_PLAN.search(s) else next(
                (n for n in NUMBER.findall(s) if _counts(n) and not _mentioned(n, known)), None)
            if missing:
                out.append((s, f"your records don't show {missing.rstrip('.,')}"))
            elif not paid and PAYMENT.search(s) and not NEGATION.search(s) and not PLAN.search(s):
                out.append((s, "your records show no payment or signed commitment yet"))
    return list(dict.fromkeys(out))


def unsupported_claims(v: Venture, r: Rehearsal, limit: int = 3) -> list[str]:
    """The feedback's list of claims the records don't support."""
    return [f"{quote(s)}: {why}." for s, why in find_unsupported(v, [m.text for m in team_messages(r)])][:limit]


def weak_spots(v: Venture, limit: int = 3) -> list[str]:
    """The riskiest open assumptions with weak evidence, most severe first: the problems a challenger reports."""
    out = []
    for h in overview.key_assumptions(v, limit=len(v.hypotheses)):
        if not h.status.is_open or h.rung >= Rung.DID:
            continue
        severity = {Importance.FATAL: "Severe: if it is wrong, the venture fails",
                    Importance.HIGH: "High: much of the plan depends on it"}.get(h.importance, "Medium")
        x = overview.next_test(v, h)
        settle = x.method if x else ("interviews that name who said what" if h.rung < Rung.SAID
                                     else "something customers do: sign-ups, a pilot, a letter of intent or a payment")
        label = h.rung.label.split(" · ")[-1].lower()
        out.append(f"{h.statement}. Evidence so far: {label}. {severity}. What would settle it: {settle}.")
    return out[:limit]


# ---- feedback without AI: keyword checks per rubric dimension (simplified) ----
PAST = re.compile(r"\b(?:last time|last (?:year|month|week|semester|spring|fall|summer|may|june)|when did|did you|"
                  r"have you ever|what happened|tell me about|walk me through|how did you|what did you)\b", re.I)
HYPOTHETICAL = re.compile(r"\b(?:would you|will you|could you see yourself|do you think you|"
                          r"if (?:there|we|you|it) (?:was|were|had|built|made|offered|existed))\b", re.I)
LEADING = re.compile(r"\b(?:don't you|wouldn't you|isn't it|aren't you|wouldn't it|you'd agree)\b|right\s*\?", re.I)
OPEN_START = re.compile(r"^\W*(?:what|how|why|when|where|who|which|tell me|walk me|describe)\b", re.I)
SPECIFIC = re.compile(r"\b(?:how (?:much|many|often|long)|what did (?:it|that) cost|exactly)\b", re.I)
PITCH = re.compile(r"\b(?:our (?:app|product|platform|service|solution|startup)|we (?:offer|built|provide|charge)|"
                   r"we're building|we are building|imagine an app)\b", re.I)
NEXT_STEP = re.compile(r"\b(?:follow up|follow-up|check in|introduce|introduction|can i (?:send|show|call|email|text)|"
                       r"next week|try (?:it|the)|sign up|be willing|email you|text you|stay in touch)\b", re.I)
EVIDENCE = re.compile(r"\b(?:interview(?:ed|s)?|survey(?:ed)?|signed|sign-?ups?|used|tried|pilot|paid|"
                      r"pre-?order(?:ed|s)?|deposits?|letters? of intent|approved)\b", re.I)
HYPE = re.compile(r"\b(?:everyone|everybody|loves? it|would pay|will pay|definitely|obviously|huge market|"
                  r"no competition)\b", re.I)
HONEST = re.compile(r"\b(?:don't know|do not know|not yet|haven't|have not|not sure|we're testing|we are testing|"
                    r"no one has|nobody has|good point|fair point|you're right)\b", re.I)
PROBLEM = re.compile(r"\b(?:problem|struggl\w*|pain\w*|hassle|waste\w*|frustrat\w*|end up|have to)\b", re.I)
MODEL = re.compile(r"\$\d|\b(?:price|fee|revenue|subscription|margin|charge|per (?:item|user|month|year))\b", re.I)
COMPETITION = re.compile(r"\b(?:compet\w*|alternatives?|instead|marketplace|versus|unlike|other apps?)\b", re.I)
TEAM = re.compile(r"\b(?:our team|we are|we're (?:two|three|four)|i'm a|background|experience|co-?founders?)\b", re.I)
ASK = re.compile(r"\b(?:we're asking|we are asking|we need|we'd use|prize|funding|raise|our ask)\b", re.I)


def _clamp(x: float) -> int:
    return int(max(1, min(5, round(x))))


def _ratio(good: int, total: int, none: int = 2) -> int:
    """1 to 5 from the share of good items; `none` when there is nothing to judge."""
    return none if total <= 0 else _clamp(1 + 4 * max(0, good) / total)


def _level(pattern: re.Pattern, text: str) -> int:
    """2 = not mentioned, 3 = once, 4 = twice or more."""
    n = len(pattern.findall(text))
    return 2 if n == 0 else 3 if n == 1 else 4


def _has_number(text: str) -> bool:
    return any(_counts(n) or n.strip("$%").isdigit() for n in NUMBER.findall(text))


def _customer_scores(v: Venture, r: Rehearsal) -> dict[str, int]:
    team = [m.text for m in team_messages(r)]
    past = sum(bool(PAST.search(t)) for t in team)
    hypothetical = sum(bool(HYPOTHETICAL.search(t)) and not NEXT_STEP.search(t) for t in team)
    opened = sum(any(OPEN_START.search(s) for s in sentences(t)) for t in team)
    leading = sum(bool(LEADING.search(t)) for t in team)
    said = sum(len(t.split()) for t in team)
    heard = sum(len(m.text.split()) for m in r.messages[1:] if m.author == CHARACTER)
    share = said / max(1, said + heard) - (0.1 if r.scenario == "solution" else 0)
    listening = 5 if share <= .35 else 4 if share <= .45 else 3 if share <= .55 else 2 if share <= .7 else 1
    if r.scenario != "solution" and any(PITCH.search(t) for t in team):
        listening -= 1
    return {"past": _ratio(past, past + hypothetical), "open": _ratio(opened - leading, len(team)),
            "listening": _clamp(listening), "specifics": _clamp(2 + sum(len(SPECIFIC.findall(t)) for t in team)),
            "next_step": 4 if NEXT_STEP.search(" ".join(team[-2:])) else 2}


def _answer_ok(text: str) -> bool:
    words = len(text.split())
    return 8 <= words <= 150 and bool(EVIDENCE.search(text) or _has_number(text) or HONEST.search(text))


def _judge_scores(v: Venture, r: Rehearsal) -> dict[str, int]:
    team = [m.text for m in team_messages(r)]
    sc = scenario_of(r)
    answers = team[1:] if sc.pitch_seconds else team
    text = " ".join(team)
    unsupported = bool(unsupported_claims(v, r))
    evidence = 2 + bool(EVIDENCE.search(text)) + _has_number(text) - bool(HYPE.search(text)) - unsupported
    model = 2 + bool(MODEL.search(text)) + (bool(MODEL.search(text)) and _has_number(text))
    timing = pitch_timing(r)
    if timing is not None:
        delivery = 2 if timing.seconds > timing.target * 1.2 else 3 if timing.over or timing.seconds < timing.target / 2 \
            else 4
    else:
        average = sum(len(a.split()) for a in answers) / max(1, len(answers))
        delivery = 4 if 15 <= average <= 90 else 3
    return {"problem": _level(PROBLEM, text), "evidence": _clamp(evidence), "model": _clamp(model),
            "competition": _level(COMPETITION, text), "team_ask": 2 + bool(TEAM.search(text)) + bool(ASK.search(text)),
            "delivery": delivery, "answers": _ratio(sum(_answer_ok(a) for a in answers), len(answers))}


def _challenger_scores(v: Venture, r: Rehearsal) -> dict[str, int]:
    team = [m.text for m in team_messages(r)]
    unsupported = len(unsupported_claims(v, r))
    honest = sum(bool(HONEST.search(t)) for t in team)
    checked = any(_has_number(t) for t in team)
    consistency = max(1, 4 - unsupported) if unsupported else (5 if checked else 4)
    average = sum(len(t.split()) for t in team) / max(1, len(team))
    return {"honesty": _clamp(2 + min(honest, 3) - bool(unsupported)),
            "evidence": _ratio(sum(bool(EVIDENCE.search(t) or _has_number(t)) for t in team), len(team)),
            "consistency": consistency, "clarity": 4 if 10 <= average <= 80 else 3 if average < 10 else 2}


SCORERS = {"customer": _customer_scores, "judge": _judge_scores, "challenger": _challenger_scores}


def verdict(score: float) -> str:
    if score >= 4:
        return "A strong session. Take the fix below into the real conversation."
    if score >= 3:
        return "A solid start, with clear things to fix."
    return "A tough session, and that is what practice is for: work on the fixes and try again."


def _advice(question: str) -> str:
    low = question.lower()
    if re.search(r"paid|pre-?order|signed|actually done|commit", low):
        return "Say exactly what customers did, with numbers; if nobody has paid yet, say so and name the test."
    if re.search(r"how many|how much|worth|cost|price|money|number", low):
        return "Give the number and where it comes from, and mark it as a guess if it is one."
    if re.search(r"who else|compet|switch|alternative|instead", low):
        return "Name what customers use today, including doing nothing, and the one thing you do better."
    if re.search(r"team|why you", low):
        return "Say what this team has done that others haven't, in one sentence."
    return "Answer directly first, then give your strongest evidence: who, how many, what they did."


def tough_questions(r: Rehearsal, limit: int = 3) -> list[str]:
    """The character's questions that got the weakest answers, each with how to answer it better."""
    pairs = []
    for i, m in enumerate(r.messages[:-1]):
        said = sentences(m.text.replace(DEMO_MARK, ""))
        last = max((k for k, s in enumerate(said) if s.endswith("?")), default=-1)
        answer = r.messages[i + 1]
        if m.author == CHARACTER and last >= 0 and answer.author != CHARACTER:
            question = " ".join(said[max(0, last - 1):last + 1]) if len(said[last].split()) < 6 else said[last]
            pairs.append((_answer_ok(answer.text), i, question))
    pairs.sort()
    return [f"{quote(q)} → {_advice(q)}" for _, _, q in pairs[:limit]]


def customer_checks(r: Rehearsal, limit: int = 3) -> list[str]:
    """What the made-up customer said that is worth checking with real customers (it is not evidence)."""
    name = first_name(r) or "The customer"
    said = [s for m in r.messages[1:] if m.author == CHARACTER and DEMO_MARK not in m.text for s in sentences(m.text)
            if not s.endswith("?") and (_has_number(s) or re.search(r"\b(?:last|usually|always|never|just|I \w+ed)\b", s))]
    return [f"{name} said {quote(s, 120)}: check whether real customers say the same." for s in said[:limit]]


def plain_feedback(v: Venture, r: Rehearsal) -> RehearsalFeedback:
    """Feedback without AI: keyword checks per rubric dimension, the records check, and the rubric's own advice.
    Marked as simplified."""
    s = spec(r.character)
    raw = SCORERS[s.id](v, r) if s.id in SCORERS else {}
    scores = {d.id: _clamp(raw.get(d.id, 3)) for d in s.rubric}
    best_first = sorted(s.rubric, key=lambda d: -scores[d.id])
    worst_first = sorted(s.rubric, key=lambda d: scores[d.id])
    strengths = [d.good for d in best_first if scores[d.id] >= 4 and d.good][:2]
    fixes = [d.fix for d in worst_first if scores[d.id] <= 3 and d.fix][:3] or [worst_first[0].fix]
    fb = RehearsalFeedback(scores=scores, overall=overall(scores), strengths=strengths, fixes=[f for f in fixes if f],
                           hints_used=len(r.hints), simplified=True)
    fb.verdict = verdict(fb.overall)
    if s.sees == SEGMENT:
        fb.checks = customer_checks(r)
    else:
        fb.tough_questions = tough_questions(r)
        fb.unsupported_claims = unsupported_claims(v, r)
    if s.sees == RECORDS:
        fb.problems = weak_spots(v)
    return fb


def plain_hint(v: Venture, r: Rehearsal) -> str:
    """A hint without AI, from what the team just did."""
    s = spec(r.character)
    team = team_messages(r)
    last = team[-1].text if team else ""
    tip = s.tips[len(r.hints) % len(s.tips)] if s.tips else "Take a breath and answer the question that was asked."
    if s.sees == SEGMENT:
        if HYPOTHETICAL.search(last) and not NEXT_STEP.search(last):
            return "That was a \"would you\" question. Ask about the last time it happened instead."
        if team and not any(SPECIFIC.search(m.text) for m in team):
            return "Ask for a number: how often, how much, how long?"
        if turns(r) >= s.wrap_after - 2:
            return "Time to close: ask for a next step, such as a follow-up or an introduction."
        return tip
    if scenario_of(r).pitch_seconds and not team:
        return "Lead with the problem and who has it, then your evidence, then your ask. Aim for about 400 words."
    if HYPE.search(last):
        return "\"Everyone\" and \"would pay\" sound like opinions. Say how many people did what."
    if s.sees == RECORDS:
        strongest = max((i for h in v.hypotheses for i in h.evidence_items if i.direction == Direction.FOR),
                        key=lambda i: i.rung, default=None)
        if strongest is not None and len(r.hints) % 2 == 0:
            return f"Your strongest evidence: \"{strongest.text}\" ({strongest.rung.label.lower()}). Lead with it."
        return "If you don't know, say so, and say how you will find out."
    return tip
