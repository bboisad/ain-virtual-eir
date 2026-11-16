"""Domain model for a venture workspace.

One group = one venture. Everything the EIR remembers lives on `Venture`.
Pure data + small queries only: no Streamlit, no I/O, no formatting.

Adding a field: give it a default value so older saved ventures still load (see serde.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from uuid import uuid4

from .clock import timestamp

EIR = "eir"  # author id used for messages written by the lead mentor (the Virtual EIR)
CONSULTANT = "consultant"  # author id used inside a consultation for the consultant's messages
CHARACTER = "character"  # author id used inside a practice session for the AI character's messages
SYSTEM = "system"  # author id for notes in the mentor chat, e.g. "switched to the Optimize mentor"


class Stage(str, Enum):
    IDEA = "Idea"
    VALIDATION = "Customer validation"
    MVP = "MVP"
    FUNDRAISING = "Fundraising"


class VentureType(str, Enum):
    MARKET = "Market-driven"
    RESEARCH = "Research commercialization"


class Mode(str, Enum):
    EXPLORE = "Explore"
    VALIDATE = "Validate"
    PREPARE = "Prepare"


class Module(str, Enum):
    """Position on the AIN Foundry Roadmap. The order of the members is the order of the roadmap."""
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    ALUMNI = "Alumni"


class Rung(IntEnum):
    """Evidence ladder (design v0.2): how strongly a claim is supported. Names the rung before treating anything as validation."""
    NONE = 0
    ASSERTION = 1
    SECONDARY = 2
    SAID = 3
    DID = 4
    PAID = 5
    RETAINED = 6

    @property
    def label(self) -> str:
        """What the models, prompts and evaluation read ("3 · Customers said"). Students see `plain`."""
        return RUNG_LABELS[self]

    @property
    def plain(self) -> str:
        """The name students see: "Customer statements · Level 3" (design: name first, the level as a detail)."""
        return RUNG_NAMES[self] if self == Rung.NONE else f"{RUNG_NAMES[self]} · Level {int(self)}"


RUNG_LABELS = {
    Rung.NONE: "Not answered",
    Rung.ASSERTION: "1 · Assertion",
    Rung.SECONDARY: "2 · Desk research",
    Rung.SAID: "3 · Customers said",
    Rung.DID: "4 · Customers did",
    Rung.PAID: "5 · Customers paid",
    Rung.RETAINED: "6 · Retained behavior",
}
RUNG_NAMES = {
    Rung.NONE: "Not graded yet",
    Rung.ASSERTION: "Assumption",
    Rung.SECONDARY: "Desk research",
    Rung.SAID: "Customer statements",
    Rung.DID: "Observed behavior",
    Rung.PAID: "Payment",
    Rung.RETAINED: "Repeat use",
}


class Verdict(str, Enum):
    READY = "Ready to move on"
    NOT_YET = "Not yet"


class ReviewState(str, Enum):
    """Human calibration of the Virtual EIR's judgments (first judgments are checked by an AIN EIR)."""
    NONE = "No EIR check needed"
    PENDING = "Awaiting EIR check"
    CONFIRMED = "Confirmed by EIR"
    REOPENED = "Reopened by EIR"


class Evidence(str, Enum):
    """How well a canvas entry is supported. Completeness is never a viability score."""
    EMPTY = "Empty"
    STATEMENT = "Student statement"
    HYPOTHESIS = "Hypothesis"
    EVIDENCE = "Evidence-backed"


class HypothesisStatus(str, Enum):
    UNTESTED = "Untested"
    TESTING = "Testing"
    SUPPORTED = "Supported"
    REFUTED = "Refuted"
    INCONCLUSIVE = "Inconclusive"

    @property
    def is_open(self) -> bool:
        return self in (HypothesisStatus.UNTESTED, HypothesisStatus.TESTING)


class StepStatus(str, Enum):
    OPEN = "open"
    DONE = "done"


class EventKind(str, Enum):
    MILESTONE = "milestone"
    SESSION = "session"
    DECISION = "decision"
    UPDATE = "update"
    APPROVAL = "approval"
    BRIEF = "brief"


# ---- multi-mentor design (v0.16). Enum values are saved in venture files: add values, never rename them. ----
class LeadMode(str, Enum):
    """Which lead mentor coaches the venture. The student chooses; the system recommends."""
    LAUNCH = "Launch"  # mentor A: from an idea to an initial launch, on the Foundry roadmap
    OPTIMIZE = "Optimize"  # mentor B: grade 6 lenses, find the bottleneck, test it


class Traction(str, Enum):
    """Project creation, question 1: has anyone outside the team signed up, tried or paid?"""
    YES = "Yes, some have"
    NOT_YET = "Not yet"
    UNSURE = "Not sure"


class Goal(str, Enum):
    """Project creation, question 2: what does the team need first?"""
    SHAPE = "Shape an idea into a plan"
    IMPROVE = "Improve something that already runs"


class Importance(IntEnum):
    """How much the venture depends on an assumption. FATAL: if it is wrong, the project fails."""
    UNRATED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    FATAL = 4


class Direction(str, Enum):
    FOR = "for"
    AGAINST = "against"
    UNCLEAR = "unclear"  # converted v0.15 evidence whose direction was never recorded


class ExperimentStatus(str, Enum):
    DRAFT = "Draft"  # criteria can still change
    RUNNING = "Running"  # criteria are locked
    CONCLUDED = "Concluded"  # the mentor judged the result against the criteria
    STOPPED = "Stopped"  # ended without a conclusion, e.g. replaced by a new experiment


class Conclusion(str, Enum):
    NONE = ""
    SUPPORTED = "Supported"
    REFUTED = "Refuted"
    INCONCLUSIVE = "Inconclusive"


class FocusKind(str, Enum):
    NONE = ""
    QUESTION = "question"  # a Foundry key question id
    ASSUMPTION = "assumption"  # a hypothesis id
    CANVAS = "canvas"  # a canvas block name
    LENS = "lens"  # an Optimize lens id


class RecordKind(str, Enum):
    """Records the lead mentor maintains. Every change to one is logged (undo, "Recent changes")."""
    FOCUS = "focus"
    ASSUMPTION = "assumption"
    EXPERIMENT = "experiment"
    TASK = "task"
    CANVAS = "canvas"
    LENS = "lens"
    DIAGNOSIS = "diagnosis"
    ANSWER = "answer"  # a Foundry key question's answer, in the team's words


class MessageKind(str, Enum):
    CHAT = "chat"
    EVENT = "event"  # a note in the chat, e.g. the mentor was switched


class ConsultationStatus(str, Enum):
    OPEN = "In progress"
    DONE = "Done"


class RehearsalStatus(str, Enum):
    OPEN = "In progress"
    DONE = "Done"


class Difficulty(str, Enum):
    FRIENDLY = "Friendly"  # patient, gives the student room
    REALISTIC = "Realistic"
    TOUGH = "Tough"  # short, skeptical, presses hard


class FileKind(str, Enum):
    """Project files: documents only, never code (design section 6)."""
    PDF = "pdf"
    WORD = "docx"
    SLIDES = "pptx"
    SHEET = "xlsx"
    CSV = "csv"
    TEXT = "text"  # .txt and .md
    IMAGE = "image"  # kept, not read in this version
    LINK = "link"  # a URL and what the team says it is; never opened

    @property
    def readable(self) -> bool:
        return self not in (FileKind.IMAGE, FileKind.LINK)


CANVAS_BLOCKS: tuple[str, ...] = (
    "Customer Segments", "Value Propositions", "Channels", "Customer Relationships", "Revenue Streams",
    "Key Resources", "Key Activities", "Key Partnerships", "Cost Structure",
)

MODULE_MODE = {  # the coaching lens follows the roadmap module
    Module.M1: Mode.EXPLORE,
    Module.M2: Mode.VALIDATE,
    Module.M3: Mode.PREPARE,
    Module.ALUMNI: Mode.PREPARE,
}

BACKGROUNDS = ("Undergraduate", "Master's student", "PhD / Postdoc", "Faculty", "Staff", "Other")


@dataclass
class Member:
    id: str  # id inside this venture, e.g. "m1"
    name: str
    background: str = "Other"
    account: str = ""  # login account that may open this venture (see eir/access.py)
    experience: str = ""  # student profile: prior venture experience, e.g. "First venture"

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def initials(self) -> str:
        parts = self.name.split()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


@dataclass
class CanvasEntry:
    text: str = ""
    status: Evidence = Evidence.EMPTY  # v0.15 label, kept so old data loads; the rung below replaces it
    source: str = ""  # who / when, e.g. "Carol · Oct 9"
    rung: Rung = Rung.NONE  # graded by the Virtual EIR, never by the student
    why: str = ""  # the reason for the rung
    updated: str = ""  # date label


@dataclass
class EvidenceItem:
    """One piece of evidence for or against an assumption. The rung says what kind of evidence it is,
    whatever it shows: "0 of 10 paid" is rung 5 evidence against."""
    text: str
    direction: Direction = Direction.FOR
    rung: Rung = Rung.ASSERTION
    source: str = ""  # e.g. "Bob · Oct 5" or "experiment X-fee"
    date: str = ""
    experiment_id: str = ""


@dataclass
class Hypothesis:
    """An assumption (the UI says "assumption"). Its rung and its conclusion are kept separate."""
    id: str
    statement: str
    owner: str  # member id
    status: HypothesisStatus = HypothesisStatus.UNTESTED  # the conclusion, separate from the rung
    evidence: str = ""  # v0.15 free text, kept so old data loads; see evidence_items
    source: str = ""
    rung: Rung = Rung.ASSERTION  # strongest evidence so far, for or against
    test: str = ""  # v0.15 free text; experiments replace it
    importance: Importance = Importance.UNRATED
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    updated: str = ""  # date label
    lens: str = ""  # Optimize: the lens it belongs to, if any


@dataclass
class NextStep:
    """A task in the Action Plan. Completing a task never validates an assumption."""
    id: str
    text: str
    owner: str  # member id, or "team"
    from_session: str  # date label of the session or day it came from, e.g. "Oct 5"
    status: StepStatus = StepStatus.OPEN
    done_by: str | None = None
    due_date: str = ""  # optional ISO date, YYYY-MM-DD
    result: str = ""  # observed outcome; completion does not validate a hypothesis
    created_by: str = ""  # member id or EIR
    experiment_id: str = ""  # set when the task belongs to an experiment
    source: str = ""
    file_id: str = ""  # a revision the mentor suggested for this project file; checked against its next version


@dataclass
class SessionRecord:
    date: str
    mode: Mode
    attendees: list[str]
    summary: str
    messages: list[Message] = field(default_factory=list)
    reviewed_by: str = ""  # a named reviewer, not a claim of unanimous team consent


@dataclass
class Event:
    date: str
    kind: EventKind
    text: str
    by: str = "team"  # member id, "team" or "AIN"


@dataclass
class Disagreement:
    """Two members hold opposite views; shown until the linked hypothesis is resolved."""
    hypothesis_id: str
    topic: str
    a_member: str
    a_says: str
    b_member: str
    b_says: str


@dataclass
class SharedBrief:
    """A Mentor Brief the team approved for sharing. The only venture content AIN staff can read."""
    date: str
    topic: str
    text: str
    approved_by: str  # member id


@dataclass
class Message:
    author: str  # member id, EIR, CONSULTANT or SYSTEM: whose words these are
    text: str
    entered_by: str | None = None  # in a team meeting, the signed-in member who typed it for `author`
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=timestamp)
    mentor: LeadMode | None = None  # the lead mentor of the chat it belongs to (None: Launch, v0.15 data)
    kind: MessageKind = MessageKind.CHAT
    change_groups: list[str] = field(default_factory=list)  # record changes this mentor message made (Undo)
    consultation_id: str = ""  # the message opened or reports on this consultation
    suggested_mode: LeadMode | None = None  # the mentor suggests switching to this lead mentor (the team decides)
    event: str = ""  # on a note: the event the mentor must answer ("summary:K-1a2b3c"); kept so a failed reply can retry
    file_id: str = ""  # the member attached this project file ...
    file_version: int = 0  # ... in this version
    rehearsal_id: str = ""  # the note sends, or the mentor's reply reports on, this practice session's feedback
    practice_suggestion: str = ""  # the mentor suggests a practice session ("judge/pitch"; see practice.Suggestion)


@dataclass
class NoteRevision:
    text: str
    by: str  # member id of the person who saved or accepted the text
    date: str
    source: str = ""  # optional originating message / discussion reference


@dataclass
class VentureProfile:
    """The venture's "business card", built in the intake interview (design doc F01).
    Everything here is what the team *says*; evidence levels live on the canvas and hypotheses."""
    self_description: str = ""  # the team's own words, as first typed
    one_liner: str = ""
    problem: str = ""
    customer: str = ""
    solution: str = ""
    alternatives: str = ""
    evidence: str = ""
    revenue: str = ""
    need: str = ""
    skipped: list[str] = field(default_factory=list)  # questions the team chose to skip for now
    notes: dict[str, str] = field(default_factory=dict)  # EIR's skeptical note per answer, e.g. "no numbers yet"
    completed_by: str | None = None  # member id
    completed_on: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.completed_on is not None


@dataclass
class Answer:
    """The team's current answer to one key question of a deliverable, graded on the evidence ladder."""
    text: str = ""
    rung: Rung = Rung.NONE
    source: str = ""  # who / when, e.g. "Bob · Oct 14"
    why: str = ""  # the Virtual EIR's reason for the rung


@dataclass
class StepJudgment:
    """The Virtual EIR's judgment of whether a deliverable is complete (design v0.2 §5)."""
    deliverable: str  # deliverable id, see eir/roadmap.py
    date: str
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    consider: list[str] = field(default_factory=list)  # "if I were you I would also…" (the team decides)
    requested_by: str = ""  # member id
    review: ReviewState = ReviewState.NONE
    reviewer: str = ""  # AIN EIR display name
    note: str = ""


@dataclass
class LearningEntry:
    """Learning log: an insight the student reached, in their own words."""
    date: str
    by: str  # member id
    text: str


@dataclass
class ModeChoice:
    """The two questions asked when the project was created, the system's recommendation and the student's choice."""
    traction: Traction | None = None
    goal: Goal | None = None
    recommended: LeadMode | None = None
    chosen: LeadMode | None = None
    by: str = ""  # member id
    date: str = ""


@dataclass
class ModeSwitch:
    date: str
    from_mode: LeadMode
    to_mode: LeadMode
    by: str  # member id
    reason: str = ""


@dataclass
class Focus:
    """The one thing the lead mentor is pressing now (Overview block 1 and the Mentor briefing)."""
    text: str = ""
    kind: FocusKind = FocusKind.NONE
    ref: str = ""  # key question id, hypothesis id, canvas block or lens id
    set_by: str = ""
    set_at: str = ""  # date label


@dataclass
class Experiment:
    """A validation experiment. Criteria are agreed before it starts and locked while it runs.
    The mentor, not the team, judges the result against them."""
    id: str = field(default_factory=lambda: f"X-{uuid4().hex[:6]}")
    assumption_id: str = ""
    lens: str = ""  # Optimize: the lens it tests
    method: str = ""
    supported_if: str = ""
    refuted_if: str = ""  # anything between the two is inconclusive
    method_rung: Rung = Rung.NONE  # the evidence this method produces, whatever the outcome
    owner: str = "team"
    deadline: str = ""  # ISO date
    status: ExperimentStatus = ExperimentStatus.DRAFT
    result: str = ""
    result_by: str = ""
    conclusion: Conclusion = Conclusion.NONE
    judged_why: str = ""
    replaces: str = ""  # id of the experiment this one replaced
    stop_reason: str = ""
    created_by: str = ""
    created_at: str = ""  # date label
    started_at: str = ""
    ended_at: str = ""

    @property
    def is_open(self) -> bool:
        return self.status in (ExperimentStatus.DRAFT, ExperimentStatus.RUNNING)


@dataclass
class LensGrade:
    """Optimize: one of the six lenses, graded on the evidence ladder by the mentor."""
    rung: Rung = Rung.NONE
    summary: str = ""
    why: str = ""
    updated: str = ""


@dataclass
class Diagnosis:
    """Optimize: the bottleneck lens and why it is the bottleneck."""
    bottleneck: str = ""  # lens id
    why: str = ""
    set_at: str = ""


@dataclass
class Change:
    """One change to a record, with before/after snapshots. Undo works per group (one mentor action)."""
    id: str = field(default_factory=lambda: f"C-{uuid4().hex[:10]}")
    group: str = ""
    kind: RecordKind = RecordKind.FOCUS
    record_id: str = ""
    summary: str = ""  # e.g. "Assumption H2: evidence 3 → 5"
    before: dict | None = None  # None: the record did not exist
    after: dict | None = None
    position: int = -1  # list index of the record, to put it back on undo
    by: str = ""  # EIR or member id
    source: str = ""  # what the change was based on
    created_at: str = field(default_factory=timestamp)
    undone_by: str = ""
    undone_at: str = ""


@dataclass
class ConsultationSummary:
    """The consultant's fixed-format summary. The lead mentor receives this, never the transcript."""
    question: str = ""
    conclusions: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    suggested_todos: list[str] = field(default_factory=list)
    needs_human: bool = False
    human_topic: str = ""
    disagreements: list[str] = field(default_factory=list)  # where the student disagreed
    out_of_scope: list[str] = field(default_factory=list)  # questions the consultant left for the lead mentor
    student_note: str = ""  # the one line the student added before sending
    written_at: str = ""


@dataclass
class Consultation:
    """The lead mentor's brief, the student's free chat with one consultant, and the summary sent back."""
    id: str = field(default_factory=lambda: f"K-{uuid4().hex[:6]}")
    consultant: str = ""  # consultant id, see knowledge/consultants.json
    question: str = ""
    brief: str = ""  # written by the lead mentor
    file_ids: list[str] = field(default_factory=list)
    requested_by: str = ""  # EIR or the member who asked for it
    status: ConsultationStatus = ConsultationStatus.OPEN
    messages: list[Message] = field(default_factory=list)  # never shown to the lead mentor
    proposed_end: bool = False  # the consultant thinks the brief is answered
    draft: ConsultationSummary | None = None  # the summary the student is previewing; a new message discards it
    summary: ConsultationSummary | None = None  # the summary sent to the lead mentor
    started_at: str = field(default_factory=timestamp)
    ended_at: str = ""
    ended_by: str = ""


@dataclass
class FileVersion:
    """One upload of a project file. The bytes and the extracted text live in the file store (eir/filestore.py),
    never in the venture record; the mentor reads the summary and opens the text only when it needs detail."""
    number: int = 1
    by: str = ""  # member id
    at: str = field(default_factory=timestamp)
    size: int = 0  # bytes
    sha256: str = ""
    blob: str = ""  # file store key of the original; its text is stored under blob + ".txt"
    chars: int = 0  # length of the extracted text; 0 = nothing readable
    summary: str = ""  # written at upload; for links, what the team says the link is
    claims: list[str] = field(default_factory=list)  # the document's key claims, in its words (claims, not evidence)
    note: str = ""  # what the member wrote with the upload


@dataclass
class ProjectFile:
    """A document the team shares with its mentor: deck, plan, interview notes, survey, sheet, screenshot or link."""
    id: str = field(default_factory=lambda: f"F-{uuid4().hex[:6]}")
    name: str = ""  # the latest version's file name
    kind: FileKind = FileKind.TEXT
    url: str = ""  # links only
    versions: list[FileVersion] = field(default_factory=list)  # oldest first
    created_by: str = ""

    @property
    def latest(self) -> FileVersion | None:
        return self.versions[-1] if self.versions else None

    def version(self, number: int) -> FileVersion | None:
        return next((x for x in self.versions if x.number == number), None)


@dataclass
class RehearsalFeedback:
    """Written by the practice coach (not the character) when a practice session ends. The student sees it first and may
    send it, never the conversation, to the lead mentor."""
    overall: float = 0.0  # mean of the scores, 1 to 5
    scores: dict[str, int] = field(default_factory=dict)  # rubric dimension id -> 1..5 (knowledge/practice.json)
    verdict: str = ""  # one line
    strengths: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)  # the three most important, each with how to do it
    tough_questions: list[str] = field(default_factory=list)  # "the question → a stronger answer"
    problems: list[str] = field(default_factory=list)  # challenger: weak spots found, most severe first
    checks: list[str] = field(default_factory=list)  # customer: what to check with real customers (not evidence)
    unsupported_claims: list[str] = field(default_factory=list)  # what the student said that the records don't support
    hints_used: int = 0
    simplified: bool = False  # written without AI (keyword checks)
    written_at: str = ""


@dataclass
class Rehearsal:
    """A practice session with an AI character: the team's own, never seen by the mentors or AIN staff, never
    evidence. Only its feedback can be sent to the lead mentor."""
    id: str = field(default_factory=lambda: f"R-{uuid4().hex[:6]}")
    character: str = ""  # character id, see knowledge/practice.json
    scenario: str = ""
    difficulty: Difficulty = Difficulty.REALISTIC
    file_ids: list[str] = field(default_factory=list)  # material the character has read (judge, challenger)
    assumption_id: str = ""  # challenger: the assumption it attacks
    persona: str = ""  # who the character is, in one line ("Maya, a junior moving out of a triple room")
    persona_profile: str = ""  # details made up at the start, so every answer stays consistent
    messages: list[Message] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    status: RehearsalStatus = RehearsalStatus.OPEN
    wrapped_up: bool = False  # the character has what it needs
    started_by: str = ""
    started_at: str = field(default_factory=timestamp)
    ended_at: str = ""
    feedback: RehearsalFeedback | None = None
    shared_at: str = ""  # when a member sent the feedback to the lead mentor
    shared_by: str = ""
    shared_note: str = ""  # the one line the member added when sending it


@dataclass
class DaySummary:
    """One day of the mentor chat in 2–3 sentences: the briefing's "last time", and context for long chats."""
    day: str  # ISO date
    label: str  # e.g. "Oct 5"
    summary: str
    mentor: LeadMode = LeadMode.LAUNCH
    messages: int = 0


@dataclass
class Venture:
    id: str
    name: str
    description: str
    stage: Stage
    type: VentureType
    members: list[Member]
    canvas: dict[str, CanvasEntry] = field(default_factory=lambda: {b: CanvasEntry() for b in CANVAS_BLOCKS})
    hypotheses: list[Hypothesis] = field(default_factory=list)
    next_steps: list[NextStep] = field(default_factory=list)
    sessions: list[SessionRecord] = field(default_factory=list)
    timeline: list[Event] = field(default_factory=list)
    disagreements: list[Disagreement] = field(default_factory=list)
    ip_sensitive: bool = False  # e.g. lab IP managed by UR Ventures: never collect technical details
    shared_briefs: list[SharedBrief] = field(default_factory=list)
    mode: Mode | None = None
    conversation: list[Message] = field(default_factory=list)  # current, not yet reviewed session
    meeting: list[str] = field(default_factory=list)  # members present at a team meeting at one screen; [] = solo
    handoff: str | None = None  # pending reason to involve a human mentor
    profile: VentureProfile = field(default_factory=VentureProfile)
    notebook: str = ""  # editable working notes; never automatically treated as verified claims
    notebook_revisions: list[NoteRevision] = field(default_factory=list)
    module: Module = Module.M1  # AIN Foundry Roadmap position
    answers: dict[str, Answer] = field(default_factory=dict)  # key question id -> current answer
    done: list[str] = field(default_factory=list)  # deliverable ids the Virtual EIR judged complete
    judgments: list[StepJudgment] = field(default_factory=list)  # oldest first
    graduation: str = ""  # "" | "requested" | "returned: <note>" | "approved" (all EIRs must agree)
    learning_log: list[LearningEntry] = field(default_factory=list)
    next_eir_session: str = ""  # ISO date of the next human EIR Foundry session, if scheduled
    # ---- multi-mentor design (v0.16) ----
    lead_mode: LeadMode = LeadMode.LAUNCH
    mode_choice: ModeChoice = field(default_factory=ModeChoice)
    mode_history: list[ModeSwitch] = field(default_factory=list)
    optimize_suggested_on: str = ""  # date the Launch mentor suggested switching (it suggests once)
    focus: Focus = field(default_factory=Focus)
    lenses: dict[str, LensGrade] = field(default_factory=dict)  # Optimize: lens id -> grade
    diagnosis: Diagnosis = field(default_factory=Diagnosis)
    experiments: list[Experiment] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    consultations: list[Consultation] = field(default_factory=list)
    day_summaries: list[DaySummary] = field(default_factory=list)
    files: list[ProjectFile] = field(default_factory=list)  # project files: names, versions and summaries only
    rehearsals: list[Rehearsal] = field(default_factory=list)  # practice sessions: the team's own
    schema: int = 1  # data version; eir/migrate.py upgrades older data on load

    # ---- lookups ----
    def file(self, file_id: str) -> ProjectFile | None:
        return next((f for f in self.files if f.id == file_id), None)

    def rehearsal(self, rehearsal_id: str) -> Rehearsal | None:
        return next((r for r in self.rehearsals if r.id == rehearsal_id), None)

    def experiment(self, experiment_id: str) -> Experiment | None:
        return next((x for x in self.experiments if x.id == experiment_id), None)

    def consultation(self, consultation_id: str) -> Consultation | None:
        return next((c for c in self.consultations if c.id == consultation_id), None)

    def open_consultation(self, consultant: str) -> Consultation | None:
        return next((c for c in self.consultations
                     if c.consultant == consultant and c.status == ConsultationStatus.OPEN), None)

    def thread(self, mode: LeadMode) -> list[Message]:
        """The mentor chat of one lead mentor (messages without a mentor tag belong to Launch)."""
        return [m for m in self.conversation if (m.mentor or LeadMode.LAUNCH) == mode]

    def member_for_account(self, account_id: str) -> Member | None:
        return next((m for m in self.members if m.account and m.account == account_id), None)

    def member(self, member_id: str) -> Member | None:
        return next((m for m in self.members if m.id == member_id), None)

    def display_name(self, member_id: str) -> str:
        m = self.member(member_id)
        if m:
            return m.first_name
        return "the team" if member_id in ("team", "any") else member_id

    def hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        return next((h for h in self.hypotheses if h.id == hypothesis_id), None)

    def step(self, step_id: str) -> NextStep | None:
        return next((s for s in self.next_steps if s.id == step_id), None)

    # ---- derived state ----
    @property
    def recommended_mode(self) -> Mode:
        return MODULE_MODE[self.module]

    @property
    def current_mode(self) -> Mode:
        return self.mode or self.recommended_mode

    @property
    def last_session(self) -> SessionRecord | None:
        return self.sessions[-1] if self.sessions else None

    def answer(self, question_id: str) -> Answer:
        return self.answers.get(question_id) or Answer()

    def open_steps(self) -> list[NextStep]:
        return [s for s in self.next_steps if s.status == StepStatus.OPEN]

    def open_disagreements(self) -> list[Disagreement]:
        return [d for d in self.disagreements
                if (h := self.hypothesis(d.hypothesis_id)) is not None and h.status.is_open]

    def count_canvas(self, status: Evidence) -> int:
        return sum(e.status == status for e in self.canvas.values())
