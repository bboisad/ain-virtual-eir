"""Records the mentor keeps: evidence for and against, rungs graded (never chosen by a member), lenses, tasks."""
import pytest

from eir import actions, records
from eir.coach.scripted import ScriptedCoach
from eir.grading import method_rung
from eir.models import EIR, Direction, HypothesisStatus, Rung, StepStatus
from eir.seed import demo_ventures


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


def test_rung_is_the_strongest_evidence_either_way_and_the_conclusion_stays_separate():
    v = campus()
    h = v.hypothesis("H2")
    assert h.rung == Rung.SAID and h.status == HypothesisStatus.TESTING
    records.add_evidence(v, "H2", "0 of 10 movers prepaid $3", Direction.AGAINST, Rung.PAID, by=EIR)
    assert h.rung == Rung.PAID and h.status == HypothesisStatus.TESTING  # the rung moved, the conclusion did not
    records.add_evidence(v, "H2", "A friend said it sounds great", Direction.FOR, Rung.ASSERTION, by=EIR)
    assert h.rung == Rung.PAID


def test_evidence_and_focus_are_validated():
    v = campus()
    with pytest.raises(ValueError):
        records.add_evidence(v, "H2", "   ", Direction.FOR, Rung.SAID, by=EIR)
    with pytest.raises(ValueError):
        records.add_evidence(v, "H99", "4 of 5 said so", Direction.FOR, Rung.SAID, by=EIR)
    with pytest.raises(ValueError):
        records.set_focus(v, "Something", "question", "no_such_question", by=EIR)


def test_member_canvas_edit_is_graded_by_the_virtual_eir():
    v = campus()
    entry = actions.edit_canvas_text(v, ScriptedCoach(), "Customer Relationships",
                                     "We help each mover in person at the table", "m3")
    assert entry.rung == Rung.ASSERTION and entry.why  # no source given: the team's belief
    entry = actions.edit_canvas_text(v, ScriptedCoach(), "Cost Structure",
                                     "According to the campus facilities website, storage costs $40 per week", "m3")
    assert entry.rung == Rung.SECONDARY
    with pytest.raises(PermissionError):
        actions.edit_canvas_text(v, ScriptedCoach(), "Cost Structure", "Free", "outsider")


def test_bottleneck_needs_a_graded_lens():
    v = campus()
    with pytest.raises(ValueError):
        records.set_bottleneck(v, "business_model", "Weakest", by=EIR)
    records.grade_lens(v, "business_model", Rung.SAID, "Sellers said they want it free", "interviews only", by=EIR)
    records.set_bottleneck(v, "business_model", "Nobody has paid yet", by=EIR)
    assert v.diagnosis.bottleneck == "business_model"
    with pytest.raises(ValueError):
        records.grade_lens(v, "no_such_lens", Rung.SAID, "", "", by=EIR)


def test_tasks_need_a_member_owner_and_completing_one_validates_nothing():
    v = campus()
    with pytest.raises(ValueError):
        records.add_task(v, "Call Res Life", "stranger", by=EIR)
    with pytest.raises(ValueError):
        records.add_task(v, "Call Res Life", "m3", by=EIR, due_date="next week")
    t = records.add_task(v, "Call Res Life about storage", "m3", by=EIR, due_date="2026-11-20")
    records.complete_task(v, t.id, by="m3", result="Storage room available for $40 a week")
    assert t.status == StepStatus.DONE and t.result.startswith("Storage room")
    assert v.hypothesis("H2").status == HypothesisStatus.TESTING


@pytest.mark.parametrize("method, rung", [
    ("Interview 5 movers about whether they would pay $3", Rung.SAID),
    ("Ask 10 movers to sign up on a waitlist", Rung.DID),
    ("Offer prepaid $3 listings to 10 movers", Rung.PAID),
    ("Collect a $3 deposit from 20 sellers", Rung.PAID),
    ("Count how many sellers come back for a second order", Rung.RETAINED),
    ("Read the census data on campus housing", Rung.SECONDARY),
])
def test_method_rung_rates_what_the_method_observes_not_its_outcome(method, rung):
    assert method_rung(method).rung == rung
