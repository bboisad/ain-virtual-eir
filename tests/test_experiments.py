"""Experiments: criteria agreed before the start, locked while running, judged by the mentor; the rung comes from the
method, whatever the outcome."""
import pytest

from eir import actions, experiments
from eir.coach.scripted import ScriptedCoach
from eir.models import EIR, Conclusion, Direction, ExperimentStatus, HypothesisStatus, Rung
from eir.seed import demo_ventures


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


def test_seeded_fee_test_runs_and_a_failed_payment_test_is_rung_5_evidence_against():
    v = campus()
    x = v.experiment("X-fee")
    assert x.status == ExperimentStatus.DRAFT and x.method_rung == Rung.PAID
    actions.start_experiment(v, "X-fee", "m1")
    assert x.status == ExperimentStatus.RUNNING
    with pytest.raises(ValueError):  # criteria are locked once it runs
        actions.edit_experiment(v, ScriptedCoach(), "X-fee", "m1", supported_if="2 or more prepay")
    actions.record_experiment_result(v, "X-fee", "m1", "2 of 10 movers prepaid")
    with pytest.raises(PermissionError):  # the team does not judge its own result
        experiments.judge(v, "X-fee", Conclusion.SUPPORTED, "Looks fine", by="m1")
    experiments.judge(v, "X-fee", Conclusion.REFUTED, "2 is below the 4 of 10 agreed in advance", by=EIR)
    h = v.hypothesis("H2")
    assert x.status == ExperimentStatus.CONCLUDED and h.status == HypothesisStatus.REFUTED
    last = h.evidence_items[-1]
    assert (last.direction, last.rung, last.experiment_id) == (Direction.AGAINST, Rung.PAID, "X-fee")
    assert h.rung == Rung.PAID


def test_a_draft_needs_both_criteria_and_a_rated_method_before_it_starts():
    v = campus()
    x = actions.add_experiment(v, ScriptedCoach(), "m2", "Ask 10 movers to sign up for a pickup", assumption_id="H1")
    assert x.method_rung == Rung.DID  # rated by the Virtual EIR, not by the team
    with pytest.raises(ValueError) as err:
        actions.start_experiment(v, x.id, "m2")
    assert "supports" in str(err.value) and "refutes" in str(err.value)
    actions.edit_experiment(v, ScriptedCoach(), x.id, "m2", supported_if="5 or more sign up",
                            refuted_if="2 or fewer sign up")
    actions.start_experiment(v, x.id, "m2")
    assert x.status == ExperimentStatus.RUNNING
    with pytest.raises(PermissionError):
        actions.edit_experiment(v, ScriptedCoach(), x.id, "m2", method_rung=Rung.RETAINED)


def test_stop_and_replace_opens_a_new_draft_with_the_same_content():
    v = campus()
    actions.start_experiment(v, "X-fee", "m1")
    new = actions.stop_experiment(v, "X-fee", "m1", "Res Life moved the table to December")
    old = v.experiment("X-fee")
    assert old.status == ExperimentStatus.STOPPED and old.stop_reason.startswith("Res Life")
    assert new.status == ExperimentStatus.DRAFT and new.replaces == "X-fee" and new.supported_if == old.supported_if
    actions.edit_experiment(v, ScriptedCoach(), new.id, "m1", supported_if="3 or more of 10 prepay")
    assert new.supported_if == "3 or more of 10 prepay"
    with pytest.raises(ValueError):
        actions.stop_experiment(v, "X-fee", "m1", "Again")


def test_a_result_needs_a_running_experiment_and_finishing_its_task_concludes_nothing():
    v = campus()
    with pytest.raises(ValueError):
        actions.record_experiment_result(v, "X-fee", "m1", "2 of 10 prepaid")  # still a draft
    actions.complete_step(v, "S2", "m1", result="Ran the table on Saturday")
    assert v.experiment("X-fee").status == ExperimentStatus.DRAFT
    assert v.hypothesis("H2").status == HypothesisStatus.TESTING


def test_starting_an_experiment_marks_an_untested_assumption_as_testing():
    v = campus()
    h = actions.add_assumption(v, "Buyers will pick items up themselves", "m3")
    assert h.status == HypothesisStatus.UNTESTED and h.rung == Rung.ASSERTION
    x = actions.add_experiment(v, ScriptedCoach(), "m3", "Offer 10 buyers a pickup slot and count sign-ups",
                               assumption_id=h.id, supported_if="7 or more sign up", refuted_if="3 or fewer sign up")
    actions.start_experiment(v, x.id, "m3")
    assert h.status == HypothesisStatus.TESTING
    with pytest.raises(PermissionError):
        actions.start_experiment(v, x.id, "outsider")
