"""The records the lead mentor keeps up to date: the current focus, assumptions and their evidence, the canvas,
the Optimize lenses and diagnosis, and tasks.

Every write goes through `changes.track`, so it appears in "Recent changes" and a mentor's write can be undone.
Callers decide who may write: `eir/actions.py` checks membership for students; the mentor writes as `EIR`.
Evidence rungs are set by the mentor or by grading the student's text; a student never picks a rung.
"""
from __future__ import annotations

import re
from datetime import date
from uuid import uuid4

from . import changes, roadmap
from .clock import today
from .models import (CANVAS_BLOCKS, EIR, Answer, CanvasEntry, Diagnosis, Direction, EvidenceItem, Focus, FocusKind,
                     Hypothesis, HypothesisStatus, Importance, LensGrade, NextStep, RecordKind, Rung, StepStatus,
                     Venture)
from .modes import lens, lens_ids


def check_due(due_date: str) -> str:
    """An optional ISO date (YYYY-MM-DD); raises ValueError when malformed."""
    due_date = (due_date or "").strip()
    if due_date:
        date.fromisoformat(due_date)
    return due_date


def _who(v: Venture, by: str) -> str:
    return "Virtual EIR" if by == EIR else v.display_name(by)


def _assumption(v: Venture, hid: str) -> Hypothesis:
    h = v.hypothesis(hid)
    if h is None:
        raise ValueError(f"Unknown assumption {hid}")
    return h


def _check_owner(v: Venture, owner: str) -> None:
    if owner != "team" and v.member(owner) is None:
        raise ValueError("The owner must be a team member or the team")


# ---- focus ----
def set_focus(v: Venture, text: str, kind: FocusKind, ref: str, *, by: str, group: str = "",
              source: str = "") -> Focus:
    text, kind = text.strip(), FocusKind(kind)
    if not text:
        raise ValueError("Describe the focus in one line")
    known = {FocusKind.NONE: True, FocusKind.QUESTION: roadmap.question(ref) is not None,
             FocusKind.ASSUMPTION: v.hypothesis(ref) is not None, FocusKind.CANVAS: ref in CANVAS_BLOCKS,
             FocusKind.LENS: ref in lens_ids()}[kind]
    if not known:
        raise ValueError(f"Unknown {kind.value}: {ref}")
    with changes.track(v, RecordKind.FOCUS, "", by=by, group=group, source=source,
                       summary=f"Focus: {v.focus.text or '(none)'} → {text}"):
        v.focus = Focus(text, kind, ref, by, today())
    return v.focus


# ---- assumptions ----
def _next_assumption_id(v: Venture) -> str:
    """H1, H2, …; a number is never reused, even after an undo removed the assumption."""
    used = [h.id for h in v.hypotheses] + [c.record_id for c in v.changes if c.kind == RecordKind.ASSUMPTION]
    numbers = [int(m.group(1)) for x in used if (m := re.fullmatch(r"H(\d+)", x))]
    return f"H{max(numbers, default=0) + 1}"


def add_assumption(v: Venture, statement: str, *, by: str, owner: str = "team",
                   importance: Importance = Importance.UNRATED, lens_id: str = "", group: str = "",
                   source: str = "") -> Hypothesis:
    statement = statement.strip()
    if not statement:
        raise ValueError("Write the assumption as one sentence")
    _check_owner(v, owner)
    if lens_id and lens_id not in lens_ids():
        raise ValueError(f"Unknown lens: {lens_id}")
    hid = _next_assumption_id(v)
    with changes.track(v, RecordKind.ASSUMPTION, hid, by=by, group=group, source=source,
                       summary=f"New assumption {hid}: {statement}"):
        v.hypotheses.append(Hypothesis(hid, statement, owner, source=f"{_who(v, by)} · {today()}",
                                       importance=Importance(importance), updated=today(), lens=lens_id))
    return _assumption(v, hid)


def update_assumption(v: Venture, hid: str, *, by: str, statement: str | None = None,
                      importance: Importance | None = None, group: str = "", source: str = "") -> Hypothesis:
    """Reword an assumption or rate how much depends on it. Its rung and conclusion change only through evidence."""
    h = _assumption(v, hid)
    parts = []
    new_statement = statement.strip() if statement is not None else h.statement
    if not new_statement:
        raise ValueError("Write the assumption as one sentence")
    if new_statement != h.statement:
        parts.append(f'reworded to "{new_statement}"')
    if importance is not None and Importance(importance) != h.importance:
        parts.append(f"importance {h.importance.name.lower()} → {Importance(importance).name.lower()}")
    if not parts:
        return h
    with changes.track(v, RecordKind.ASSUMPTION, hid, by=by, group=group, source=source,
                       summary=f"Assumption {hid}: " + "; ".join(parts)):
        h.statement = new_statement
        if importance is not None:
            h.importance = Importance(importance)
        h.updated = today()
    return h


def add_evidence(v: Venture, hid: str, text: str, direction: Direction, rung: Rung, *, by: str, group: str = "",
                 source: str = "", experiment_id: str = "") -> EvidenceItem:
    """Record evidence for or against an assumption. The assumption's rung is its strongest evidence either way."""
    h = _assumption(v, hid)
    text, direction, rung = text.strip(), Direction(direction), Rung(rung)
    if not text:
        raise ValueError("Describe the evidence: who, how many, what they did")
    if rung == Rung.NONE:
        raise ValueError("Evidence needs a rung")
    old = h.rung
    item = EvidenceItem(text, direction, rung, source or f"{_who(v, by)} · {today()}", today(), experiment_id)
    note = f"; level {int(old)} → {int(max(old, rung))}" if rung > old else ""
    with changes.track(v, RecordKind.ASSUMPTION, hid, by=by, group=group, source=source,
                       summary=f"Assumption {hid}: evidence {direction.value} ({rung.label}){note}"):
        h.evidence_items.append(item)
        h.rung = Rung(max(old, rung))
        h.updated = today()
    return item


def set_status(v: Venture, hid: str, status: HypothesisStatus, *, by: str, group: str = "",
               source: str = "") -> Hypothesis:
    """The assumption's conclusion (Testing / Supported / Refuted / Inconclusive), kept apart from its rung."""
    h = _assumption(v, hid)
    status = HypothesisStatus(status)
    if status != h.status:
        with changes.track(v, RecordKind.ASSUMPTION, hid, by=by, group=group, source=source,
                           summary=f"Assumption {hid}: {h.status.value} → {status.value}"):
            h.status, h.updated = status, today()
    return h


# ---- Foundry key questions (Launch) ----
def record_answer(v: Venture, question_id: str, text: str, rung: Rung, why: str, *, by: str, group: str = "",
                  source: str = "") -> Answer:
    """A key question's answer in the team's words, with the Virtual EIR's grade. The step check reads these."""
    q = roadmap.question(question_id)
    if q is None:
        raise ValueError(f"Unknown key question: {question_id}")
    text, rung = text.strip(), Rung(rung)
    if not text:
        raise ValueError("Write the team's answer in their own words")
    if rung == Rung.NONE:
        raise ValueError("Grade the answer on the evidence ladder (1-6)")
    old = v.answer(question_id)
    with changes.track(v, RecordKind.ANSWER, question_id, by=by, group=group, source=source,
                       summary=f"Key question \"{q.ask[:60]}\": level {int(old.rung)} → {int(rung)}"):
        v.answers[question_id] = Answer(text, rung, f"{_who(v, by)} · {today()}", why.strip())
    return v.answers[question_id]


# ---- canvas (Launch) ----
def update_canvas(v: Venture, block: str, *, by: str, text: str | None = None, rung: Rung | None = None,
                  why: str = "", group: str = "", source: str = "") -> CanvasEntry:
    if block not in CANVAS_BLOCKS:
        raise ValueError(f"Unknown canvas block: {block}")
    old = v.canvas.get(block) or CanvasEntry()
    new_text = old.text if text is None else text.strip()
    new_rung = Rung.NONE if not new_text else (old.rung if rung is None else Rung(rung))
    parts = (["text updated"] if new_text != old.text else []) + (
        [f"level {int(old.rung)} → {int(new_rung)}"] if new_rung != old.rung else [])
    if not parts and (not why or why == old.why):
        return old
    attribution = old.source if new_text == old.text else f"{_who(v, by)} · {today()}"
    with changes.track(v, RecordKind.CANVAS, block, by=by, group=group, source=source,
                       summary=f"Canvas · {block}: " + (", ".join(parts) or "reason updated")):
        v.canvas[block] = CanvasEntry(new_text, old.status, attribution, new_rung, why.strip() or old.why, today())
    return v.canvas[block]


# ---- lenses and diagnosis (Optimize) ----
def grade_lens(v: Venture, lens_id: str, rung: Rung, summary: str, why: str, *, by: str, group: str = "",
               source: str = "") -> LensGrade:
    x = lens(lens_id)
    if x is None:
        raise ValueError(f"Unknown lens: {lens_id}")
    old = v.lenses.get(lens_id) or LensGrade()
    rung = Rung(rung)
    with changes.track(v, RecordKind.LENS, lens_id, by=by, group=group, source=source,
                       summary=f"Lens · {x.title}: level {int(old.rung)} → {int(rung)}"):
        v.lenses[lens_id] = LensGrade(rung, summary.strip(), why.strip(), today())
    return v.lenses[lens_id]


def set_bottleneck(v: Venture, lens_id: str, why: str, *, by: str, group: str = "",
                   source: str = "") -> Diagnosis:
    x = lens(lens_id)
    if x is None:
        raise ValueError(f"Unknown lens: {lens_id}")
    if lens_id not in v.lenses:
        raise ValueError("Grade this lens before naming it the bottleneck")
    if not why.strip():
        raise ValueError("Say why this lens is the bottleneck")
    with changes.track(v, RecordKind.DIAGNOSIS, "", by=by, group=group, source=source,
                       summary=f"Bottleneck: {x.title}"):
        v.diagnosis = Diagnosis(lens_id, why.strip(), today())
    return v.diagnosis


# ---- tasks ----
def add_task(v: Venture, text: str, owner: str, *, by: str, due_date: str = "", experiment_id: str = "",
             file_id: str = "", group: str = "", source: str = "") -> NextStep:
    """A task; with `file_id` it is a revision suggested for that project file (checked against its next version)."""
    text = text.strip()
    if not text:
        raise ValueError("A task needs a description")
    _check_owner(v, owner)
    if file_id and v.file(file_id) is None:
        raise ValueError(f"Unknown project file {file_id}")
    due_date = check_due(due_date)
    sid = f"S-{uuid4().hex[:12]}"
    summary = f"New revision for {v.file(file_id).name}: {text}" if file_id else f"New task: {text}"
    with changes.track(v, RecordKind.TASK, sid, by=by, group=group, source=source, summary=summary):
        v.next_steps.append(NextStep(sid, text, owner, today(), due_date=due_date, created_by=by,
                                     experiment_id=experiment_id, source=source, file_id=file_id))
    return v.step(sid)


def update_task(v: Venture, sid: str, *, by: str, owner: str, due_date: str = "", result: str = "",
                group: str = "", source: str = "") -> NextStep:
    """Change a task's owner, due date or reported result. It stays open: completing is a separate step."""
    s = v.step(sid)
    if s is None:
        raise ValueError("This task does not exist")
    _check_owner(v, owner)
    due_date = check_due(due_date)
    with changes.track(v, RecordKind.TASK, sid, by=by, group=group, source=source, summary=f"Task updated: {s.text}"):
        s.owner, s.due_date, s.result = owner, due_date, result.strip()
    return s


def complete_task(v: Venture, sid: str, *, by: str, result: str = "", group: str = "",
                  source: str = "") -> NextStep:
    """Mark a task done and keep its result. Completing a task does not validate an assumption."""
    s = v.step(sid)
    if s is None:
        raise ValueError("This task does not exist")
    with changes.track(v, RecordKind.TASK, sid, by=by, group=group, source=source, summary=f"Done: {s.text}"):
        s.status, s.done_by = StepStatus.DONE, by
        s.result = result.strip() or s.result
    return s
