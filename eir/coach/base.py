"""The coach interface. The UI depends only on this, so scripted and AI coaches are interchangeable."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..grading import Grade
from ..models import (Consultation, ConsultationSummary, FileVersion, Message, ProjectFile, Rehearsal,
                      RehearsalFeedback, Venture)
from ..tools import ToolBox


@dataclass(frozen=True)
class LeadEvent:
    """Something outside the chat that the lead mentor should act on."""
    kind: str  # "invite": a member asked for a consultant · "summary": a consultation came back · "judge": a result
    ref: str  # consultant id, consultation id or experiment id


@dataclass
class LeadTurn:
    text: str


@dataclass
class ConsultTurn:
    text: str
    propose_end: bool = False  # the consultant thinks the brief is answered and offers to write the summary


@dataclass
class FileSummary:
    summary: str  # what the mentor reads instead of the document most of the time
    claims: list[str] = field(default_factory=list)  # the document's key claims, with the evidence it gives


@dataclass
class PracticeStart:
    """How a practice character opens a session: its first line and, for a target customer, who they are."""
    opening: str
    persona: str = ""  # one line, e.g. "Maya, a junior moving out of a triple room"
    persona_profile: str = ""  # the details that keep the customer's answers consistent


@dataclass
class PracticeTurn:
    text: str
    wrap_up: bool = False  # the character has what it needs and closes the session


class Coach(Protocol):
    label: str  # shown in the UI, e.g. "Scripted demo" or "claude-sonnet-5-5"

    def suggestions(self, v: Venture, speaker: str) -> list[str]:
        """Prepared example messages the speaker can send with one click (fictional demo ventures)."""

    def grade_evidence(self, v: Venture, question: str, answer: str) -> Grade:
        """The Virtual EIR grades the evidence behind a team's answer on the 6-rung ladder."""

    def rate_method(self, v: Venture, method: str) -> Grade:
        """Action Plan: the evidence an experiment's method can produce, whatever its result."""

    def lead_turn(self, v: Venture, box: ToolBox, event: LeadEvent | None = None) -> LeadTurn:
        """The lead mentor's reply to the latest team message (or to an event). Record updates go through `box`."""

    def summarize_day(self, v: Venture, label: str, messages: list[Message]) -> str:
        """Two or three sentences on one day of the mentor chat (the briefing's "last time")."""

    # ---- consultants: they see the brief and a read-only overview (access.consultant_view), never the mentor chat,
    # and change no records ----
    def consult_turn(self, v: Venture, c: Consultation) -> ConsultTurn:
        """The consultant's reply to the latest team message in the consultation."""

    def consult_summary(self, v: Venture, c: Consultation) -> ConsultationSummary:
        """The fixed-format summary for the lead mentor, written from the consultation."""

    def consult_suggestions(self, v: Venture, c: Consultation, speaker: str) -> list[str]:
        """Prepared messages to the consultant for the fictional demo ventures."""

    # ---- project files ----
    def summarize_file(self, v: Venture, f: ProjectFile, version: FileVersion, text: str,
                       previous: FileVersion | None = None) -> FileSummary:
        """The summary and key claims of an uploaded version (and what changed since `previous`). Never blocks the
        upload: implementations fall back to a plain summary."""

    # ---- practice characters: they see only access.character_view (`material` is the text of the files the team
    # chose, see practice.material), get no actions, and nothing they say is evidence ----
    def practice_start(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeStart:
        """The persona (target customer) and the opening line of a new session. Never fails: falls back to the
        scenario's template."""

    def practice_turn(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeTurn:
        """The character's reply to the team's latest message."""

    def practice_feedback(self, v: Venture, r: Rehearsal, material: str = "") -> RehearsalFeedback:
        """The practice coach's feedback on the session: scores per rubric dimension, what worked, three fixes, and
        the checks against the records. Falls back to practice.plain_feedback."""

    def practice_hint(self, v: Venture, r: Rehearsal, material: str = "") -> str:
        """One line from the practice coach for a student who is stuck. The character never sees it."""

    def practice_suggestions(self, v: Venture, r: Rehearsal, speaker: str) -> list[str]:
        """Prepared messages for the fictional demo ventures."""
