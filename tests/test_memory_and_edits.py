"""The mentor remembers open threads; members' own edits (canvas text, tasks, assumptions) are validated, graded by
the Virtual EIR where evidence is involved, and listed under Recent changes."""
import pytest

from eir import actions, memory, overview, teams
from eir.access import Account
from eir.coach.scripted import ScriptedCoach
from eir.models import Rung, StepStatus
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


# ---- memory ----
def test_open_threads_list_disagreements_before_open_actions():
    threads = memory.open_threads(campus())
    assert "willingness to pay" in threads[0]
    assert "Has anyone paid" in threads[1] and "needs 4 · customers did" in threads[1]
    assert any("open action" in t for t in memory.open_threads(campus(), limit=5))
    assert len(memory.open_threads(campus(), limit=1)) == 1


def test_free_question_to_the_mentor_is_grounded_in_open_threads():
    v = campus()
    reply = actions.mentor_message(v, ScriptedCoach(), "m1", "what should we do about pricing?")
    assert "still open" in reply.text and "Students will happily pay $3 per item" in reply.text


def test_briefing_for_a_new_project_starts_with_the_first_key_question():
    v = teams.create_workspace(InMemoryRepository([]), Account("dana", "Dana Wu"), "Pilot", "Delivery")
    (line,) = memory.briefing(v)  # no next action, no last time, no consultation yet
    assert line.startswith("**Current focus:** What problem do they have") and line.endswith("_(Not graded yet)_")


# ---- canvas: the team writes, the Virtual EIR grades ----
def test_canvas_text_is_graded_attributed_and_listed():
    v = campus()
    actions.edit_canvas_text(v, ScriptedCoach(), "Channels", "We interviewed 12 movers; 9 found us at the table", "m3")
    entry = v.canvas["Channels"]
    assert entry.text.startswith("We interviewed 12") and entry.rung == Rung.SAID and entry.why
    assert entry.source.startswith("Carol")
    assert overview.recent_changes(v)[0].text.startswith("Canvas · Channels") and v.changes[-1].by == "m3"


def test_clearing_a_block_empties_it_and_outsiders_cannot_edit():
    v = campus()
    actions.edit_canvas_text(v, ScriptedCoach(), "Channels", "", "m1")
    assert v.canvas["Channels"].rung == Rung.NONE and not v.canvas["Channels"].text
    with pytest.raises(PermissionError):
        actions.edit_canvas_text(v, ScriptedCoach(), "Channels", "x", "outsider")
    with pytest.raises(ValueError):
        actions.edit_canvas_text(v, ScriptedCoach(), "Not a block", "x", "m1")


# ---- tasks ----
def test_tasks_keep_owner_due_date_result_and_never_validate_assumptions():
    v = campus()
    before = [(h.status, h.rung) for h in v.hypotheses]
    step = actions.add_step(v, "Interview students about their last move-out", "m2", "m1", "2026-10-20")
    assert (step.owner, step.due_date, step.created_by) == ("m2", "2026-10-20", "m1")
    actions.update_step(v, step.id, "m1", owner="team", due_date="2026-10-21", result=" 1 more done ")
    assert (step.owner, step.due_date, step.result, step.status) == ("team", "2026-10-21", "1 more done",
                                                                     StepStatus.OPEN)
    actions.complete_step(v, step.id, "m2", "Three described abandoning items in the hallway.")
    assert step.status == StepStatus.DONE and step.done_by == "m2" and "Three described" in step.result
    assert [(h.status, h.rung) for h in v.hypotheses] == before
    assert overview.recent_changes(v)[0].text == f"Done: {step.text}"


def test_task_validation_happens_before_changes():
    v = campus()
    count, logged = len(v.next_steps), len(v.changes)
    for owner, actor in (("outsider", "m1"), ("m1", "outsider")):
        with pytest.raises(PermissionError):
            actions.add_step(v, "Interview", owner, actor)
    with pytest.raises(ValueError):
        actions.add_step(v, " ", "m1", "m1")
    with pytest.raises(ValueError):
        actions.add_step(v, "Interview", "m1", "m1", "next Tuesday")
    with pytest.raises(PermissionError):
        actions.complete_step(v, "S1", "outsider")
    with pytest.raises(ValueError):
        actions.complete_step(v, "missing", "m1")
    with pytest.raises(ValueError):
        actions.update_step(v, "S1", "m1", owner="team", due_date="next week", result="")
    assert len(v.next_steps) == count and len(v.changes) == logged


# ---- assumptions: the words are the team's, the evidence level is the mentor's ----
def test_a_member_adds_and_rewords_an_assumption_without_setting_its_evidence():
    v = campus()
    h = actions.add_assumption(v, "Movers will list items a week before they leave", "m2")
    assert (h.id, h.owner, h.rung) == ("H4", "m2", Rung.ASSERTION)
    actions.edit_assumption(v, "H4", "Movers will list items two weeks before they leave", "m2")
    assert v.hypothesis("H4").statement.endswith("two weeks before they leave")
    with pytest.raises(PermissionError):
        actions.add_assumption(v, "x", "outsider")
