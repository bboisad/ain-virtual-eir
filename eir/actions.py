"""Everything a member can do inside a venture workspace.

Pages call these functions and then save; they never edit a Venture directly.
Every function that changes data checks that the acting person is a member. Record changes go through `records`
and `experiments`, so they show under "Recent changes"; other changes are logged to the timeline.
(Creating, joining and describing a project lives in `teams.py`.)
"""
from __future__ import annotations

from . import changes, consult, experiments, memory, modes, overview, practice, records, roadmap
from . import files as files_module
from .clock import today
from .coach.base import Coach, LeadEvent
from .filestore import FileStore
from .models import (CHARACTER, CONSULTANT, EIR, SYSTEM, CanvasEntry, Change, Consultation, ConsultationStatus,
                     ConsultationSummary, Difficulty, Event, EventKind, Experiment, Goal, Hypothesis, LeadMode,
                     LearningEntry, Message, MessageKind, ModeChoice, ModeSwitch, Module, NextStep, ProjectFile,
                     Rehearsal, RehearsalFeedback, RehearsalStatus, Rung, SharedBrief, StepJudgment, Traction, Venture)
from .tools import ToolBox

__all__ = ["today", "add_step", "update_step", "complete_step", "share_brief", "submit_answer", "check_step",
           "step_back", "request_graduation", "add_learning", "set_experience", "schedule_eir_session",
           # the lead mentor and consultants
           "mentor_message", "mentor_event", "pending_event", "awaiting_reply", "retry_reply",
           "choose_mode", "switch_mode", "invite_consultant", "consult_post", "end_consultation",
           "request_consultant", "consult_message", "consult_retry", "draft_summary", "keep_talking", "send_summary",
           "upload_file", "save_file", "discuss_file", "add_link", "delete_file", "undo",
           # practice with AI characters
           "start_practice", "practice_message", "practice_retry", "practice_hint", "end_practice", "keep_practising",
           "practice_again", "delete_practice", "share_practice",
           "add_experiment", "edit_experiment", "start_experiment", "stop_experiment", "record_experiment_result",
           "add_assumption", "edit_assumption", "edit_canvas_text"]


def _require_member(v: Venture, member_id: str) -> None:
    if not v.member(member_id):
        raise PermissionError("Only a member of this venture can make this change")


def _log(v: Venture, kind: EventKind, text: str, by: str) -> None:
    v.timeline.append(Event(today(), kind, text, by))


def _require_owner(v: Venture, owner: str) -> None:
    if owner != "team":
        _require_member(v, owner)


# ---- tasks (Action Plan). Completing a task never validates an assumption. ----
def add_step(v: Venture, text: str, owner: str, by: str, due_date: str = "") -> NextStep:
    _require_member(v, by)
    _require_owner(v, owner)
    return records.add_task(v, text, owner, by=by, due_date=due_date)


def update_step(v: Venture, step_id: str, by: str, owner: str, due_date: str, result: str) -> NextStep:
    _require_member(v, by)
    _require_owner(v, owner)
    return records.update_task(v, step_id, by=by, owner=owner, due_date=due_date, result=result)


def complete_step(v: Venture, step_id: str, by: str, result: str = "") -> NextStep:
    """Record completion and the observed result."""
    _require_member(v, by)
    return records.complete_task(v, step_id, by=by, result=result)


# ---- human handoff ----
def share_brief(v: Venture, topic: str, text: str, by: str) -> None:
    """Team consent: from now on AIN staff can read this brief (and only this) for the venture."""
    _require_member(v, by)
    v.shared_briefs.append(SharedBrief(today(), topic, text, by))
    _log(v, EventKind.BRIEF, f"Human EIR brief shared with AIN: {topic}", by)
    v.handoff = None


# ---- AIN Foundry Roadmap (rules in roadmap.py; the Virtual EIR judges steps, humans approve graduation) ----
def submit_answer(v: Venture, coach: Coach, question_id: str, text: str, by: str) -> Rung:
    """The team writes the answer; the Virtual EIR grades its evidence (students never grade themselves)."""
    _require_member(v, by)
    q = roadmap.question(question_id)
    if q is None:
        raise ValueError("Unknown key question")
    if not text.strip():
        raise ValueError("Write the answer (who, what, how many, where it is recorded) before saving it.")
    g = coach.grade_evidence(v, q.ask, text)
    records.record_answer(v, question_id, text, max(g.rung, Rung.ASSERTION), g.why, by=by)
    return v.answer(question_id).rung


def check_step(v: Venture, deliverable_id: str, by: str) -> StepJudgment:
    """Ask the Virtual EIR to judge whether a deliverable is complete."""
    _require_member(v, by)
    return roadmap.judge(v, deliverable_id, by)


def step_back(v: Venture, by: str, reason: str) -> Module:
    _require_member(v, by)
    return roadmap.step_back(v, by, reason)


def request_graduation(v: Venture, by: str) -> None:
    _require_member(v, by)
    roadmap.request_graduation(v, by)


def add_learning(v: Venture, text: str, by: str) -> None:
    """Learning log: an insight in the student's own words (never written by the EIR alone)."""
    _require_member(v, by)
    text = text.strip()
    if not text:
        raise ValueError("Write the insight in your own words")
    v.learning_log.append(LearningEntry(today(), by, text))


def set_experience(v: Venture, member_id: str, experience: str, by: str) -> None:
    """Student profile: a member sets their own prior venture experience."""
    _require_member(v, by)
    if member_id != by:
        raise PermissionError("You can only edit your own profile")
    v.member(member_id).experience = experience


def schedule_eir_session(v: Venture, iso_date: str, by: str) -> None:
    """Record the next human EIR Foundry session ("" clears it)."""
    _require_member(v, by)
    v.next_eir_session = records.check_due(iso_date)


# ---- talking to the lead mentor ----
def mentor_message(v: Venture, coach: Coach, author: str, text: str, files: FileStore | None = None) -> Message:
    """A member writes to the lead mentor. The mentor always replies and may update records; each update is listed on
    its reply with an Undo button. If the mentor fails, its updates are rolled back and the member's message stays.
    `files` lets the mentor open project files (read_file)."""
    _require_member(v, author)
    text = text.strip()
    if not text:
        raise ValueError("Write a message first")
    v.conversation.append(Message(author, text, mentor=v.lead_mode))
    return _lead_reply(v, coach, files=files)


def mentor_event(v: Venture, coach: Coach, by: str, event: LeadEvent, note: str = "",
                 files: FileStore | None = None) -> Message:
    """Something outside the chat the lead mentor should act on: a member asked for a consultant, a consultation
    summary came back, or an experiment result needs judging. `note` is shown in the chat first; it remembers the event,
    so the mentor can be asked again if it fails to answer."""
    if by != EIR:
        _require_member(v, by)
    if note:
        v.conversation.append(Message(SYSTEM, note, mentor=v.lead_mode, kind=MessageKind.EVENT,
                                      event=f"{event.kind}:{event.ref}",
                                      rehearsal_id=event.ref if event.kind == "practice" else ""))
    return _lead_reply(v, coach, event, files=files)


def pending_event(v: Venture) -> LeadEvent | None:
    """An event at the end of the current mentor's chat that the mentor never answered (its reply failed)."""
    thread = v.thread(v.lead_mode)
    if thread and thread[-1].author == SYSTEM and thread[-1].event:
        kind, _, ref = thread[-1].event.partition(":")
        return LeadEvent(kind, ref)
    return None


def awaiting_reply(v: Venture) -> bool:
    """The mentor has not answered the latest member message or event in its chat (its reply failed)."""
    thread = v.thread(v.lead_mode)
    return bool(thread) and (thread[-1].author not in (EIR, SYSTEM) or pending_event(v) is not None)


def retry_reply(v: Venture, coach: Coach, by: str, files: FileStore | None = None) -> Message:
    """Ask the mentor again to answer the latest message or event, after it failed to reply."""
    _require_member(v, by)
    if not awaiting_reply(v):
        raise ValueError("The Virtual EIR has already replied")
    return _lead_reply(v, coach, pending_event(v), files=files)


def _lead_reply(v: Venture, coach: Coach, event: LeadEvent | None = None, files: FileStore | None = None) -> Message:
    try:
        memory.ensure_day_summaries(v, coach)
    except Exception:  # noqa: BLE001 - a missing day summary must never block the mentor's reply
        pass
    box = ToolBox(v, files=files)
    try:
        turn = coach.lead_turn(v, box, event)
    except Exception:
        box.rollback()
        raise
    consultation = box.opened[-1] if box.opened else (event.ref if event and event.kind == "summary" else "")
    reply = Message(EIR, turn.text, mentor=v.lead_mode, change_groups=list(box.groups),
                    consultation_id=consultation, suggested_mode=box.suggested_mode,
                    rehearsal_id=event.ref if event and event.kind == "practice" else "",
                    practice_suggestion=box.suggested_practice)
    v.conversation.append(reply)
    if box.handoff:
        v.handoff = box.handoff
    return reply


# ---- lead mentor A/B ----
def choose_mode(v: Venture, by: str, chosen: LeadMode, traction: Traction | None = None,
                goal: Goal | None = None) -> ModeChoice:
    """Record the two creation questions, the system's recommendation and the student's choice of lead mentor."""
    _require_member(v, by)
    chosen = LeadMode(chosen)
    recommended = modes.recommend(traction, goal, v.type)
    v.mode_choice = ModeChoice(traction, goal, recommended, chosen, by, today())
    v.lead_mode = chosen
    note = "" if chosen == recommended else f" (recommended: the {modes.NAMES[recommended]})"
    _log(v, EventKind.DECISION, f"Chose the {modes.NAMES[chosen]}{note}", by)
    return v.mode_choice


def switch_mode(v: Venture, by: str, to: LeadMode, reason: str = "") -> ModeSwitch:
    _require_member(v, by)
    return modes.switch(v, to, by, reason)


# ---- consultations (design decision 1) ----
def _consultation(v: Venture, consultation_id: str) -> Consultation:
    c = v.consultation(consultation_id)
    if c is None:
        raise ValueError("This consultation does not exist")
    return c


def invite_consultant(v: Venture, consultant_id: str, question: str, brief: str, by: str,
                      file_ids: tuple[str, ...] = ()) -> Consultation:
    """Open a consultation with the lead mentor's brief. `by` is EIR (the mentor's idea) or the member who asked."""
    if by != EIR:
        _require_member(v, by)
    return consult.start(v, consultant_id, question, brief, by=by, file_ids=tuple(file_ids))


def consult_post(v: Venture, consultation_id: str, author: str, text: str) -> Message:
    """A member's message to a consultant (the consultant's reply comes from the coach)."""
    _require_member(v, author)
    return consult.add_message(_consultation(v, consultation_id), author, text)


def end_consultation(v: Venture, consultation_id: str, by: str, summary: ConsultationSummary,
                     note: str = "") -> Consultation:
    """Close the consultation with this summary and the member's one-line note (see also send_summary)."""
    _require_member(v, by)
    return consult.finish(v, _consultation(v, consultation_id), summary, note, by=by)


def request_consultant(v: Venture, coach: Coach, by: str, consultant_id: str,
                       files: FileStore | None = None) -> tuple[Consultation, bool]:
    """A member clicks a consultant in the rail: the lead mentor brings them in with a brief. If the mentor wrote no
    brief (or could not reply), the standard brief is used so the team is not blocked. Returns the consultation and
    whether the standard brief was used."""
    _require_member(v, by)
    spec = consult.spec(consultant_id)
    current = v.open_consultation(consultant_id)
    if current is not None:
        return current, False
    try:
        mentor_event(v, coach, by, LeadEvent("invite", consultant_id),
                     note=f"{v.display_name(by)} asked the Virtual EIR to bring in the {spec.name} consultant.", files=files)
    except Exception:  # noqa: BLE001 - the standard brief below keeps the team going
        thread = v.thread(v.lead_mode)
        if thread and thread[-1].author == SYSTEM:
            thread[-1].event = ""  # answered below: do not ask the mentor again
    c = v.open_consultation(consultant_id)
    if c is not None:
        return c, False
    question = overview.consultation_question(v, consultant_id)
    return consult.start(v, consultant_id, question, overview.consultation_brief(v, question), by=by), True


def consult_message(v: Venture, coach: Coach, consultation_id: str, author: str, text: str) -> Message:
    """A member writes to a consultant; the consultant always replies. A new message discards a summary draft.
    If the consultant fails, the member's message stays and consult_retry asks again."""
    c = _consultation(v, consultation_id)
    consult_post(v, consultation_id, author, text)
    c.draft, c.proposed_end = None, False
    return _consultant_reply(v, coach, c)


def consult_retry(v: Venture, coach: Coach, consultation_id: str, by: str) -> Message:
    _require_member(v, by)
    c = _consultation(v, consultation_id)
    if not consult.awaiting_reply(c):
        raise ValueError("The consultant has already replied")
    return _consultant_reply(v, coach, c)


def _consultant_reply(v: Venture, coach: Coach, c: Consultation) -> Message:
    turn = coach.consult_turn(v, c)
    reply = consult.add_message(c, CONSULTANT, turn.text)
    c.proposed_end = turn.propose_end
    return reply


def draft_summary(v: Venture, coach: Coach, consultation_id: str, by: str) -> ConsultationSummary:
    """The consultant writes its summary for the student to preview (nothing is sent yet)."""
    _require_member(v, by)
    c = _consultation(v, consultation_id)
    if c.status != ConsultationStatus.OPEN:
        raise ValueError("This consultation has already ended")
    summary = coach.consult_summary(v, c)
    summary.question = summary.question or c.question
    c.draft = consult.enforce(consult.spec(c.consultant), summary, consult.transcript(v, c))
    return c.draft


def keep_talking(v: Venture, consultation_id: str, by: str) -> None:
    """Back to the conversation: the draft summary is discarded."""
    _require_member(v, by)
    c = _consultation(v, consultation_id)
    c.draft, c.proposed_end = None, False


def send_summary(v: Venture, coach: Coach, consultation_id: str, by: str, note: str = "",
                 files: FileStore | None = None) -> Message:
    """The student sends the previewed summary, with one line of their own, to the lead mentor, which replies with the
    key points and the records it updates. If the mentor fails, the consultation stays closed and retry_reply asks
    the mentor again."""
    _require_member(v, by)
    c = _consultation(v, consultation_id)
    if c.draft is None:
        raise ValueError("Review the summary before sending it")
    consult.finish(v, c, c.draft, note, by=by)
    c.draft = None
    return mentor_event(v, coach, by, LeadEvent("summary", c.id),
                        note=f"{v.display_name(by)} sent the {consult.name_of(c.consultant)} consultant's summary to "
                             "the Virtual EIR.", files=files)


# ---- project files (design section 6): the team's documents; the mentor reads and suggests, never edits ----
def upload_file(v: Venture, coach: Coach, store: FileStore, by: str, name: str, data: bytes,
                note: str = "") -> Message:
    """A member attaches a file to a message in the mentor chat: it is stored (a new version when the name matches an
    earlier file), its text is extracted and summarized, and the mentor replies. Returns the mentor's reply. If the
    mentor fails, the file and the member's message stay, and retry_reply asks again."""
    f = save_file(v, store, by, name, data, note)
    return discuss_file(v, coach, store, by, f.id, note)


def save_file(v: Venture, store: FileStore, by: str, name: str, data: bytes, note: str = "") -> ProjectFile:
    """Save a document in the project folder, without a coaching turn or changes to evidence."""
    _require_member(v, by)
    f, version, text = files_module.add_version(v, store, name, data, by, note)
    version.summary = files_module.saved_summary(text, note)
    _log(v, EventKind.UPDATE, f"File {'updated' if version.number > 1 else 'shared'}: "
                             f"{f.name} (version {version.number})", by)
    return f


def discuss_file(v: Venture, coach: Coach, store: FileStore, by: str, file_id: str,
                 note: str = "") -> Message:
    """Send an existing file's latest version to the Virtual EIR, without uploading another copy.

    A failed reply leaves the attached team message available for the normal chat retry.
    """
    _require_member(v, by)
    f = v.file(file_id)
    if f is None or f.latest is None:
        raise ValueError("This project file is no longer available")
    version = f.latest
    previous = f.versions[-2] if len(f.versions) > 1 else None
    try:
        summary = coach.summarize_file(v, f, version, files_module.text(store, f, version), previous)
        version.summary, version.claims = summary.summary, list(summary.claims)
    except Exception:  # the saved excerpt is enough to start a conversation or retry it
        pass
    words = note.strip() or (f"Here is a new version of {f.name}." if previous else f"Here is {f.name}.")
    v.conversation.append(Message(by, words, mentor=v.lead_mode, file_id=f.id, file_version=version.number))
    return _lead_reply(v, coach, files=store)


def add_link(v: Venture, by: str, url: str, description: str) -> ProjectFile:
    """A link (e.g. the product page) with what it shows, in the team's words. It is never opened."""
    _require_member(v, by)
    f = files_module.add_link(v, url, description, by)
    _log(v, EventKind.UPDATE, f"Link shared: {f.url}", by)
    return f


def delete_file(v: Venture, store: FileStore, by: str, file_id: str) -> ProjectFile:
    """Remove a file with all its versions, e.g. a technical document shared by mistake."""
    _require_member(v, by)
    f = files_module.delete(v, store, file_id)
    _log(v, EventKind.UPDATE, f"File removed: {f.name}", by)
    return f


# ---- undo the mentor's record updates ----
def undo(v: Venture, group: str, by: str) -> list[Change]:
    _require_member(v, by)
    undone = changes.undo_group(v, group, by)
    _log(v, EventKind.UPDATE, f"Undid the Virtual EIR's update: {undone[0].summary}", by)
    return undone


# ---- experiments: the team writes method and criteria; the Virtual EIR rates the method; the mentor judges ----
def add_experiment(v: Venture, coach: Coach, by: str, method: str, assumption_id: str = "",
                   supported_if: str = "", refuted_if: str = "", owner: str = "team", deadline: str = "",
                   lens: str = "") -> Experiment:
    _require_member(v, by)
    return experiments.create(v, by=by, method=method, assumption_id=assumption_id, lens=lens,
                              supported_if=supported_if, refuted_if=refuted_if,
                              method_rung=coach.rate_method(v, method).rung, owner=owner, deadline=deadline)


def edit_experiment(v: Venture, coach: Coach, experiment_id: str, by: str, **fields) -> Experiment:
    _require_member(v, by)
    if "method_rung" in fields:
        raise PermissionError("The Virtual EIR rates the method. Change the method instead.")
    if "method" in fields:
        fields["method_rung"] = coach.rate_method(v, fields["method"]).rung
    return experiments.edit(v, experiment_id, by=by, **fields)


def start_experiment(v: Venture, experiment_id: str, by: str) -> Experiment:
    _require_member(v, by)
    return experiments.start(v, experiment_id, by=by)


def stop_experiment(v: Venture, experiment_id: str, by: str, reason: str, replace: bool = True) -> Experiment | None:
    _require_member(v, by)
    return experiments.stop(v, experiment_id, reason, by=by, replace=replace)


def record_experiment_result(v: Venture, experiment_id: str, by: str, result: str) -> Experiment:
    _require_member(v, by)
    return experiments.record_result(v, experiment_id, result, by=by)


# ---- members editing the mentor's records: the words are theirs, the rung is graded by the Virtual EIR ----
def add_assumption(v: Venture, statement: str, by: str) -> Hypothesis:
    """A member adds an assumption. It starts as an assertion; the mentor rates its importance."""
    _require_member(v, by)
    return records.add_assumption(v, statement, by=by, owner=by)


def edit_assumption(v: Venture, hypothesis_id: str, statement: str, by: str) -> Hypothesis:
    _require_member(v, by)
    return records.update_assumption(v, hypothesis_id, by=by, statement=statement)


def edit_canvas_text(v: Venture, coach: Coach, block: str, text: str, by: str) -> CanvasEntry:
    """A member rewrites a canvas block; the Virtual EIR grades the new text (a student never picks a rung)."""
    _require_member(v, by)
    grade = coach.grade_evidence(v, f"Business model canvas · {block}", text)
    return records.update_canvas(v, block, by=by, text=text, rung=grade.rung, why=grade.why)


# ---- practice with AI characters (eir/practice.py): the team's own, never evidence; no record changes here ----
def _rehearsal(v: Venture, rehearsal_id: str) -> Rehearsal:
    r = v.rehearsal(rehearsal_id)
    if r is None:
        raise ValueError("This practice session does not exist")
    return r


def start_practice(v: Venture, coach: Coach, by: str, character: str, scenario: str,
                   difficulty: Difficulty = Difficulty.REALISTIC, file_ids: tuple[str, ...] = (),
                   assumption_id: str = "", files: FileStore | None = None) -> Rehearsal:
    """Start a session: the character opens (a target customer is made up for each session). `files` lets the judge
    and the challenger read the chosen material."""
    _require_member(v, by)
    r = practice.new(v, character, scenario, difficulty, by=by, file_ids=tuple(file_ids), assumption_id=assumption_id)
    try:
        start = coach.practice_start(v, r, practice.material(v, files, r))
        opening = start.opening
    except Exception:  # noqa: BLE001 - the scenario's own opening keeps the team going
        start, opening = None, ""
    if not opening.strip():
        s = practice.spec(character)
        persona, profile = practice.plain_persona(v, r) if s.sees == practice.SEGMENT else ("", "")
        first = next(iter(s.asks), "")
        return practice.begin(v, r, practice.opening(v, r, first, persona), persona, profile)
    return practice.begin(v, r, opening, start.persona, start.persona_profile)


def practice_message(v: Venture, coach: Coach, rehearsal_id: str, author: str, text: str,
                     files: FileStore | None = None) -> Message:
    """A member speaks to the character, which always replies. If it fails, the member's message stays and
    practice_retry asks again."""
    _require_member(v, author)
    r = _rehearsal(v, rehearsal_id)
    practice.add_message(r, author, text)
    return _character_reply(v, coach, r, files)


def practice_retry(v: Venture, coach: Coach, rehearsal_id: str, by: str, files: FileStore | None = None) -> Message:
    _require_member(v, by)
    r = _rehearsal(v, rehearsal_id)
    if not practice.awaiting_reply(r):
        raise ValueError("The character has already replied")
    return _character_reply(v, coach, r, files)


def _character_reply(v: Venture, coach: Coach, r: Rehearsal, files: FileStore | None) -> Message:
    turn = coach.practice_turn(v, r, practice.material(v, files, r))
    reply = practice.add_message(r, CHARACTER, turn.text)
    r.wrapped_up = turn.wrap_up
    return reply


def practice_hint(v: Venture, coach: Coach, rehearsal_id: str, by: str, files: FileStore | None = None) -> str:
    """A whisper from the practice coach for a member who is stuck. The character never sees it."""
    _require_member(v, by)
    r = _rehearsal(v, rehearsal_id)
    if r.status != RehearsalStatus.OPEN:
        raise ValueError("This practice session has ended")
    try:
        text = coach.practice_hint(v, r, practice.material(v, files, r))
    except Exception:  # noqa: BLE001 - a hint must never fail
        text = ""
    return practice.add_hint(r, text.strip() or practice.plain_hint(v, r))


def end_practice(v: Venture, coach: Coach, rehearsal_id: str, by: str,
                 files: FileStore | None = None) -> RehearsalFeedback:
    """End the session: the practice coach (not the character) writes the feedback. Only the team sees it until a
    member sends it to the mentor."""
    _require_member(v, by)
    r = _rehearsal(v, rehearsal_id)
    practice.check_can_finish(r)
    try:
        feedback = coach.practice_feedback(v, r, practice.material(v, files, r))
    except Exception:  # noqa: BLE001 - ending must never lose the session
        feedback = practice.plain_feedback(v, r)
    practice.finish(v, r, feedback, by=by)
    return r.feedback


def keep_practising(v: Venture, rehearsal_id: str, by: str) -> None:
    """Continue after the character wrapped up."""
    _require_member(v, by)
    practice.keep_going(_rehearsal(v, rehearsal_id))


def practice_again(v: Venture, coach: Coach, rehearsal_id: str, by: str,
                   files: FileStore | None = None) -> Rehearsal:
    """A new session with the same settings (a target customer is a new person each time)."""
    old = _rehearsal(v, rehearsal_id)
    return start_practice(v, coach, by, old.character, old.scenario, old.difficulty,
                          tuple(fid for fid in old.file_ids if v.file(fid) is not None), old.assumption_id, files)


def delete_practice(v: Venture, rehearsal_id: str, by: str) -> Rehearsal:
    _require_member(v, by)
    return practice.delete(v, _rehearsal(v, rehearsal_id))


def share_practice(v: Venture, coach: Coach, rehearsal_id: str, by: str, note: str = "",
                   files: FileStore | None = None) -> Message:
    """A member sends a session's feedback (never the conversation), with an optional one-line note, to the lead
    mentor, which replies and may add tasks or new assumptions from it (practice is not evidence). If the mentor fails,
    the feedback stays sent and retry_reply asks the mentor again."""
    _require_member(v, by)
    r = _rehearsal(v, rehearsal_id)
    practice.share(r, by=by, note=note)
    who = practice.first_name(r) or f"the {practice.name_of(r.character).lower()}"
    return mentor_event(v, coach, by, LeadEvent("practice", r.id),
                        note=f"{v.display_name(by)} sent the feedback from a practice session with {who} "
                             f"({practice.scenario_of(r).title}) to the Virtual EIR.", files=files)
