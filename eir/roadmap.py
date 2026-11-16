"""The AIN Foundry Roadmap and the Virtual EIR's step judgment (design v0.2).

Structure: modules (M1, M2, M3) → deliverables (customer discovery, canvas, pitch deck, business plan)
→ key questions taken from the 24 steps. Each answer is graded on the evidence ladder (models.Rung).

Rules (design v0.2 §5):
1. The Virtual EIR judges whether a deliverable is complete: every key question answered at its required rung.
   The judgment gives the verdict, the reasons, and "things I would also consider" that the team may ignore.
2. Calibration: the venture's first CALIBRATION READY judgments are marked for an AIN EIR to confirm or reopen.
3. When all deliverables of a module are done, the venture moves to the next module automatically.
4. Leaving the Foundry (to NextCorps) needs all AIN EIRs to agree: only staff can approve graduation
   (see access.decide_graduation).

Content lives in knowledge/roadmap.json; AIN resources and EIR expertise areas in knowledge/ain_resources.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .clock import today
from .models import (Answer, Event, EventKind, FocusKind, HypothesisStatus, Module, ReviewState, Rung, StepJudgment,
                     Venture, Verdict, VentureType)

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
ORDER: tuple[Module, ...] = tuple(Module)  # M1, M2, M3, Alumni
CALIBRATION = 3  # first READY judgments per venture that an AIN EIR checks


@dataclass(frozen=True)
class Question:
    id: str
    ask: str
    need: Rung  # minimum evidence rung to count as answered
    step: int = 0  # Disciplined Entrepreneurship step (draft mapping); 0 = a Foundry item outside the 24 steps


@dataclass(frozen=True)
class Deliverable:
    id: str
    title: str
    steps: tuple[str, ...]  # Disciplined Entrepreneurship steps it covers
    questions: tuple[Question, ...]
    consider: tuple[str, ...]
    short: str = ""  # short name for labels, e.g. "Pitch deck"

    def step_name(self, number: int) -> str:
        """e.g. 23 -> "Show the dogs will eat the dog food" ("" when the deliverable does not list that step)."""
        return next((s.split(" ", 1)[1] for s in self.steps if s.split(" ", 1)[0] == str(number)), "")


@dataclass(frozen=True)
class ModuleInfo:
    module: Module
    title: str
    focus: str
    deliverables: tuple[Deliverable, ...] = ()

    @property
    def name(self) -> str:
        """e.g. "M2 · The Perfect Pitch" or "Graduated to NextCorps"."""
        return self.title if self.module == Module.ALUMNI else f"{self.module.value} · {self.title}"


@dataclass(frozen=True)
class Resource:
    name: str
    kind: str
    when: str


@dataclass(frozen=True)
class Progress:
    answered: int  # key questions at or above their required rung
    total: int

    @property
    def ready(self) -> bool:
        return self.total > 0 and self.answered == self.total


def _read(name: str) -> dict:
    return json.loads((KNOWLEDGE / name).read_text(encoding="utf-8"))


@lru_cache
def modules() -> dict[Module, ModuleInfo]:
    data = _read("roadmap.json")
    out = {}
    for m in data["modules"]:
        dels = tuple(Deliverable(d["id"], d["title"], tuple(d["steps"]),
                                 tuple(Question(q["id"], q["ask"], Rung(q["need"]), int(q.get("step", 0)))
                                       for q in d["questions"]),
                                 tuple(d.get("consider", [])), d.get("short") or d["title"])
                     for d in m["deliverables"])
        out[Module(m["id"])] = ModuleInfo(Module(m["id"]), m["title"], m["focus"], dels)
    a = data["alumni"]
    out[Module.ALUMNI] = ModuleInfo(Module.ALUMNI, a["title"], a["focus"])
    return out


@lru_cache
def question_chain() -> tuple[str, ...]:
    """The fixed order in which the Virtual EIR questions every claim (design v0.2 §3.3)."""
    return tuple(_read("roadmap.json")["chain"])


def info(module: Module) -> ModuleInfo:
    return modules()[module]


def deliverable(deliverable_id: str) -> Deliverable | None:
    return next((d for m in modules().values() for d in m.deliverables if d.id == deliverable_id), None)


def module_of(deliverable_id: str) -> Module:
    return next(m.module for m in modules().values() if any(d.id == deliverable_id for d in m.deliverables))


def question(question_id: str) -> Question | None:
    return next((q for m in modules().values() for d in m.deliverables for q in d.questions if q.id == question_id), None)


def deliverable_of(question_id: str) -> Deliverable | None:
    return next((d for m in modules().values() for d in m.deliverables if any(q.id == question_id for q in d.questions)), None)


def is_met(v: Venture, q: Question) -> bool:
    return v.answer(q.id).rung >= q.need


def progress(v: Venture, d: Deliverable) -> Progress:
    return Progress(sum(is_met(v, q) for q in d.questions), len(d.questions))


def current_deliverable(v: Venture) -> Deliverable | None:
    """The first deliverable of the current module that is not done yet."""
    return next((d for d in info(v.module).deliverables if d.id not in v.done), None)


def weakest(v: Venture, limit: int = 3) -> list[tuple[Question, Answer]]:
    """Key questions of the current deliverable still below their required rung.
    Claims the team made without enough evidence come first (biggest gap first), then unanswered questions."""
    d = current_deliverable(v)
    if d is None:
        return []
    gaps = [(q, v.answer(q.id)) for q in d.questions if not is_met(v, q)]
    gaps.sort(key=lambda qa: (qa[1].rung == Rung.NONE, -(qa[0].need - qa[1].rung)))
    return gaps[:limit]


def position_label(v: Venture) -> str:
    """Where the venture is on the Foundry roadmap, down to the step being pressed, e.g.
    "M2 · Pitch deck · step 23 Show the dogs will eat the dog food". The step comes from the mentor's focus when it is
    a key question of the current deliverable, otherwise from the weakest key question."""
    if v.module == Module.ALUMNI:
        return info(v.module).name
    d = current_deliverable(v)
    if d is None:
        return f"{v.module.value} · all deliverables done"
    q = question(v.focus.ref) if v.focus.kind == FocusKind.QUESTION else None
    if q is None or deliverable_of(q.id) != d:
        gaps = weakest(v, limit=1)
        q = gaps[0][0] if gaps else None
    label = f"{v.module.value} · {d.short}"
    if q is None:
        return label
    if q.step == 0:
        return f"{label} · Foundry item"
    name = d.step_name(q.step)
    return f"{label} · step {q.step}" + (f" {name}" if name else "")


def next_module(module: Module) -> Module | None:
    i = ORDER.index(module)
    return ORDER[i + 1] if i + 1 < len(ORDER) else None


def previous_module(module: Module) -> Module | None:
    i = ORDER.index(module)
    return ORDER[i - 1] if i > 0 else None


def is_done(v: Venture, module: Module) -> bool:
    return ORDER.index(module) < ORDER.index(v.module)


def roadmap_complete(v: Venture) -> bool:
    """Every deliverable of M1–M3 judged complete: the venture can ask for graduation."""
    return all(d.id in v.done for m in ORDER if m != Module.ALUMNI for d in info(m).deliverables)


def pending_reviews(v: Venture) -> list[tuple[int, StepJudgment]]:
    return [(i, j) for i, j in enumerate(v.judgments) if j.review == ReviewState.PENDING]


def last_judgment(v: Venture, deliverable_id: str) -> StepJudgment | None:
    return next((j for j in reversed(v.judgments) if j.deliverable == deliverable_id), None)


# ---- team actions (membership is checked by the caller in actions.py) ----
def answer(v: Venture, question_id: str, text: str, rung: Rung, by_name: str, why: str = "") -> None:
    q = question(question_id)
    if q is None:
        raise ValueError("Unknown key question")
    text = text.strip()
    if rung > Rung.NONE and not text:
        raise ValueError("Write the answer (who, what, how many, where it is recorded) before grading it.")
    v.answers[question_id] = Answer(text, rung if text else Rung.NONE, f"{by_name} · {today()}" if text else "",
                                    why if text else "")


def judge(v: Venture, deliverable_id: str, by: str) -> StepJudgment:
    """The Virtual EIR checks a deliverable against its key questions and records its judgment."""
    d = deliverable(deliverable_id)
    if d is None or module_of(deliverable_id) != v.module:
        raise ValueError("The Virtual EIR checks deliverables of your current module only")
    reasons, gaps = [], []
    for q in d.questions:
        a = v.answer(q.id)
        if is_met(v, q):
            reasons.append(f"OK · {q.ask} ({a.rung.label})")
        else:
            have = a.rung.label if a.rung else "not answered yet"
            gaps.append(f"Not yet · {q.ask} Needs at least {q.need.label}; you have {have}.")
    verdict = Verdict.NOT_YET if gaps else Verdict.READY
    consider = list(d.consider)
    for h in v.hypotheses:
        if h.status == HypothesisStatus.REFUTED:
            consider.append(f"Your hypothesis \"{h.statement}\" was refuted. Does this deliverable still reflect that?")
    calibrating = sum(j.verdict == Verdict.READY for j in v.judgments) < CALIBRATION
    review = ReviewState.PENDING if verdict == Verdict.READY and calibrating else ReviewState.NONE
    j = StepJudgment(d.id, today(), verdict, gaps + reasons, consider if verdict == Verdict.READY else consider[:1],
                     by, review)
    v.judgments.append(j)
    if verdict == Verdict.READY:
        if d.id not in v.done:
            v.done.append(d.id)
        v.timeline.append(Event(today(), EventKind.MILESTONE, f"Virtual EIR: {d.title} complete", by))
        _advance(v, by)
    return j


def _advance(v: Venture, by: str) -> None:
    """All deliverables of the current module done → next module (never past M3: graduation is human)."""
    while v.module != Module.ALUMNI and all(d.id in v.done for d in info(v.module).deliverables):
        nxt = next_module(v.module)
        if nxt is None or nxt == Module.ALUMNI:
            return
        v.timeline.append(Event(today(), EventKind.MILESTONE, f"Moved from {info(v.module).name} to {info(nxt).name}", by))
        v.module = nxt


def step_back(v: Venture, by: str, reason: str) -> Module:
    """The team returns to the previous module, e.g. after its core assumption was refuted."""
    reason = reason.strip()
    if not reason:
        raise ValueError("Say what changed, so your EIR understands the step back.")
    prev = previous_module(v.module)
    if prev is None or v.module == Module.ALUMNI:
        raise ValueError("You cannot step back from here")
    v.timeline.append(Event(today(), EventKind.DECISION,
                            f"Stepped back from {info(v.module).name} to {info(prev).name}: {reason}", by))
    v.module = prev
    v.done = [d for d in v.done if module_of(d) != prev]
    return prev


def request_graduation(v: Venture, by: str) -> None:
    if not roadmap_complete(v):
        raise ValueError("Complete all four deliverables before asking for the graduation review")
    v.graduation = "requested"
    v.timeline.append(Event(today(), EventKind.MILESTONE, "Asked AIN EIRs for the graduation review (NextCorps)", by))


# ---- AIN EIR actions (called only through access.py, after the staff role check) ----
def apply_review(v: Venture, index: int, confirm: bool, staff_name: str, note: str) -> StepJudgment:
    j = v.judgments[index]
    if j.review != ReviewState.PENDING:
        raise ValueError("This judgment is not waiting for an EIR check")
    note = note.strip()
    if not confirm and not note:
        raise ValueError("Tell the team what is missing before reopening the step.")
    j.reviewer, j.note = staff_name, note
    d = deliverable(j.deliverable)
    if confirm:
        j.review = ReviewState.CONFIRMED
        v.timeline.append(Event(today(), EventKind.APPROVAL, f"{staff_name} confirmed: {d.title} complete", "AIN"))
    else:
        j.review = ReviewState.REOPENED
        if j.deliverable in v.done:
            v.done.remove(j.deliverable)
        mod = module_of(j.deliverable)
        if ORDER.index(v.module) > ORDER.index(mod):
            v.module = mod
        v.timeline.append(Event(today(), EventKind.APPROVAL, f"{staff_name} reopened {d.title}: {note}", "AIN"))
    return j


def apply_graduation(v: Venture, approve: bool, staff_name: str, note: str) -> None:
    if v.graduation != "requested":
        raise ValueError("No graduation review was requested")
    note = note.strip()
    if approve:
        v.graduation, v.module = "approved", Module.ALUMNI
        v.timeline.append(Event(today(), EventKind.APPROVAL, f"All EIRs agreed: graduated to NextCorps ({staff_name})", "AIN"))
    else:
        if not note:
            raise ValueError("Tell the team what is missing.")
        v.graduation = f"returned: {note}"
        v.timeline.append(Event(today(), EventKind.APPROVAL, f"Graduation review returned by {staff_name}: {note}", "AIN"))


def review_packet(v: Venture) -> str:
    """What AIN EIRs read for the graduation review: answers and judgments, never the conversation."""
    lines = [f"# Graduation review: {v.name}", f"**Team:** {', '.join(m.name for m in v.members)}"]
    if v.ip_sensitive:
        lines.append("_IP-sensitive venture: check that no technical details were entered._")
    for m in ORDER:
        if m == Module.ALUMNI:
            continue
        for d in info(m).deliverables:
            lines.append(f"## {d.title}")
            for q in d.questions:
                a = v.answer(q.id)
                lines.append(f"- **{q.ask}** {a.text or '—'} _({a.rung.label})_")
    return "\n".join(lines)


# ---- AIN resources and human EIR routing ----
def resources(v: Venture, limit: int = 3) -> list[Resource]:
    """AIN offerings for the current module, most specific first."""
    research = v.type == VentureType.RESEARCH
    matches = [r for r in _read("ain_resources.json")["resources"]
               if v.module.value in r["modules"] and (research or not r.get("research_only"))]
    # research-specific help first for research ventures, then module-specific; stable within ties
    matches.sort(key=lambda r: (not r.get("research_only"), len(r["modules"])))
    return [Resource(r["name"], r["kind"], r["when"]) for r in matches[:limit]]


def expertise_for(topic: str) -> str:
    """Which kind of human EIR fits a handoff topic. AIN staff pick the person."""
    text = topic.lower()
    for e in _read("ain_resources.json")["eir_expertise"]:
        if any(re.search(rf"\b{re.escape(k)}", text) for k in e["keywords"]):
            return e["area"]
    return "General venture coaching"
