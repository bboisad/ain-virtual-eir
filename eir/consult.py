"""Consultants the lead mentor can bring in (multi-mentor design, decision 1).

Flow:
1. The lead mentor writes a brief.
2. The student chats freely with the consultant.
3. The consultant (or the student) ends the consultation.
4. The consultant's fixed-format summary, plus one line from the student, goes back to the lead mentor.

Rules kept here:
- One open consultation per consultant; different consultants may run in parallel.
- A brief is required.
- Must-hand-off topics always go to a human.
- The lead mentor only ever sees the summary (see access.lead_view_of_consultation).
- Consultants never change records.

Consultant skeletons live in knowledge/consultants.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .clock import timestamp, today
from .models import (CONSULTANT, Consultation, ConsultationStatus, ConsultationSummary, Event, EventKind, Message,
                     Venture)

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
NOTE_LIMIT = 280  # the student's note to the lead mentor is one line


@dataclass(frozen=True)
class ConsultantSpec:
    id: str
    name: str
    initials: str
    color: str
    scope: str
    keywords: tuple[str, ...]
    checklist: tuple[str, ...]
    red_flags: tuple[str, ...]
    evidence: tuple[tuple[int, str], ...]  # (rung, what that rung looks like in this domain)
    answer: tuple[str, ...]
    prepare_only: tuple[str, ...]
    must_hand_off: tuple[str, ...]
    hand_off_expertise: str
    opening: str

    def opening_message(self, question: str) -> str:
        return self.opening.format(question=question.rstrip(".?") + "?", first_check=self.checklist[0])


@lru_cache
def consultants() -> tuple[ConsultantSpec, ...]:
    data = json.loads((KNOWLEDGE / "consultants.json").read_text(encoding="utf-8"))["consultants"]
    return tuple(ConsultantSpec(
        c["id"], c["name"], c["initials"], c["color"], c["scope"], tuple(c["keywords"]), tuple(c["checklist"]),
        tuple(c["red_flags"]), tuple(sorted((int(k), text) for k, text in c["evidence"].items())),
        tuple(c["permissions"]["answer"]), tuple(c["permissions"]["prepare_only"]),
        tuple(c["permissions"]["must_hand_off"]), c["hand_off_expertise"], c["opening"]) for c in data)


def spec(consultant_id: str) -> ConsultantSpec:
    s = next((c for c in consultants() if c.id == consultant_id), None)
    if s is None:
        raise ValueError(f"Unknown consultant: {consultant_id}")
    return s


def name_of(consultant_id: str) -> str:
    return next((c.name for c in consultants() if c.id == consultant_id), consultant_id)


def topic_of(text: str) -> str | None:
    """The consultant whose domain a message is about (keyword match), for the rule that topics don't cross."""
    low = text.lower()
    scores = [(sum(1 for k in c.keywords if re.search(rf"\b{re.escape(k)}", low)), c.id) for c in consultants()]
    score, cid = max(scores, default=(0, None))
    return cid if score else None


def start(v: Venture, consultant_id: str, question: str, brief: str, *, by: str,
          file_ids: tuple[str, ...] = ()) -> Consultation:
    """Open a consultation with the lead mentor's brief. One open consultation per consultant."""
    s = spec(consultant_id)
    brief = brief.strip()
    if not brief:
        raise ValueError("Your Virtual EIR writes a brief before an AI consultant joins")
    question = question.strip() or brief.splitlines()[0][:160]
    if v.open_consultation(consultant_id) is not None:
        raise ValueError(f"A {s.name} consultation is already open. Continue it, or end it first.")
    c = Consultation(consultant=consultant_id, question=question, brief=brief, file_ids=list(file_ids),
                     requested_by=by)
    c.messages.append(Message(CONSULTANT, s.opening_message(question), consultation_id=c.id))
    v.consultations.append(c)
    v.timeline.append(Event(today(), EventKind.UPDATE, f"{s.name} consultant invited: {question}", by))
    return c


def add_message(c: Consultation, author: str, text: str) -> Message:
    if c.status != ConsultationStatus.OPEN:
        raise ValueError("This consultation has ended. Ask your Virtual EIR for a new one.")
    text = text.strip()
    if not text:
        raise ValueError("Write a message first")
    m = Message(author, text, consultation_id=c.id)
    c.messages.append(m)
    return m


def awaiting_reply(c: Consultation) -> bool:
    """The latest message is the team's and the consultant has not answered it (its reply failed)."""
    return c.status == ConsultationStatus.OPEN and bool(c.messages) and c.messages[-1].author != CONSULTANT


def transcript(v: Venture, c: Consultation) -> str:
    """The consultation as text, for writing its summary (never shown to the lead mentor)."""
    return "\n".join(f"{'Consultant' if m.author == CONSULTANT else v.display_name(m.author)}: {m.text}"
                     for m in c.messages)


def enforce(s: ConsultantSpec, summary: ConsultationSummary, transcript: str = "") -> ConsultationSummary:
    """Must-hand-off topics always go to a human, whatever the summary says."""
    text = " ".join([summary.question, *summary.conclusions, *summary.suggested_todos, *summary.out_of_scope,
                     transcript]).lower()
    hit = next((t for t in s.must_hand_off if t.lower() in text), None)
    if hit and not summary.needs_human:
        summary.needs_human = True
    if hit and not summary.human_topic:
        summary.human_topic = hit
    return summary


def finish(v: Venture, c: Consultation, summary: ConsultationSummary, note: str, *, by: str) -> Consultation:
    """End the consultation: the summary and the student's one-line note go back to the lead mentor."""
    if c.status != ConsultationStatus.OPEN:
        raise ValueError("This consultation has already ended")
    note = " ".join(note.split())
    if len(note) > NOTE_LIMIT:
        raise ValueError(f"Keep your note to one line ({NOTE_LIMIT} characters)")
    summary.question = summary.question or c.question
    summary.student_note = note
    summary.written_at = summary.written_at or timestamp()
    transcript = " ".join(m.text for m in c.messages)
    c.summary = enforce(spec(c.consultant), summary, transcript)
    c.status, c.ended_at, c.ended_by = ConsultationStatus.DONE, timestamp(), by
    v.timeline.append(Event(today(), EventKind.UPDATE, f"{spec(c.consultant).name} consultation ended: {c.question}", by))
    return c


@dataclass(frozen=True)
class RailItem:
    """One avatar in the consultant rail."""
    spec: ConsultantSpec
    state: str  # "unused" (greyed) | "open" (in progress) | "done"
    current: Consultation | None  # the open consultation, else the latest one


def rail(v: Venture) -> list[RailItem]:
    items = []
    for s in consultants():
        mine = [c for c in v.consultations if c.consultant == s.id]
        open_one = next((c for c in mine if c.status == ConsultationStatus.OPEN), None)
        state = "open" if open_one else ("done" if mine else "unused")
        items.append(RailItem(s, state, open_one or (mine[-1] if mine else None)))
    return items


def history(v: Venture, consultant_id: str) -> list[Consultation]:
    return [c for c in v.consultations if c.consultant == consultant_id]


def open_consultations(v: Venture) -> list[Consultation]:
    return [c for c in v.consultations if c.status == ConsultationStatus.OPEN]
