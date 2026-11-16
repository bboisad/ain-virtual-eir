"""The two lead mentors: the recommendation, Optimize's evidence check, the one-time switch suggestion, switching."""
import pytest

from eir import actions, experiments, modes, records
from eir.access import Account
from eir.coach.scripted import ScriptedCoach
from eir.models import (CANVAS_BLOCKS, EIR, SYSTEM, Goal, LeadMode, Message, MessageKind, Rung, Traction,
                        VentureType)
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures
from eir.teams import create_workspace


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


@pytest.mark.parametrize("traction, goal, venture_type, expected", [
    (Traction.YES, Goal.IMPROVE, VentureType.MARKET, LeadMode.OPTIMIZE),
    (Traction.YES, Goal.SHAPE, VentureType.MARKET, LeadMode.LAUNCH),
    (Traction.NOT_YET, Goal.IMPROVE, VentureType.MARKET, LeadMode.LAUNCH),
    (Traction.UNSURE, Goal.IMPROVE, VentureType.MARKET, LeadMode.LAUNCH),
    (Traction.YES, Goal.IMPROVE, VentureType.RESEARCH, LeadMode.LAUNCH),
])
def test_recommendation(traction, goal, venture_type, expected):
    assert modes.recommend(traction, goal, venture_type) == expected


def test_the_student_may_choose_against_the_recommendation_and_optimize_checks_the_evidence_first():
    v = create_workspace(InMemoryRepository([]), Account("dana", "Dana Park"), "Shelf", "Second-hand textbooks",
                         lead_mode=LeadMode.OPTIMIZE, traction=Traction.NOT_YET, goal=Goal.IMPROVE)
    assert v.lead_mode == LeadMode.OPTIMIZE and v.mode_choice.recommended == LeadMode.LAUNCH
    ok, best = modes.entry_check(v)
    assert not ok and best == Rung.NONE
    assert "Launch Virtual EIR" in modes.entry_message(best)


def test_launch_suggests_optimize_once_when_customers_paid_and_the_canvas_is_graded():
    v = campus()
    assert not modes.ready_for_optimize(v)
    actions.submit_answer(v, ScriptedCoach(), "pd_commitment", "6 of 15 movers paid $3 at the table", "m1")
    assert modes.customer_behavior_rung(v) == Rung.PAID
    assert not modes.ready_for_optimize(v)  # two canvas blocks are not graded yet
    for block in CANVAS_BLOCKS:
        if v.canvas[block].rung == Rung.NONE:
            records.update_canvas(v, block, by=EIR, text="Volunteers at the table", rung=Rung.ASSERTION)
    assert modes.ready_for_optimize(v)
    modes.mark_optimize_suggested(v)
    assert not modes.ready_for_optimize(v)  # suggested only once


def test_switching_keeps_every_record_and_the_earlier_chat():
    v = campus()
    v.conversation.append(Message("m1", "Earlier question to the Launch mentor"))
    hypotheses, planned = list(v.hypotheses), list(v.experiments)
    actions.switch_mode(v, "m1", LeadMode.OPTIMIZE, "We have 6 paying sellers now")
    assert v.lead_mode == LeadMode.OPTIMIZE and v.hypotheses == hypotheses and v.experiments == planned
    assert v.thread(LeadMode.LAUNCH)[-1].text == "Earlier question to the Launch mentor"
    note = v.thread(LeadMode.OPTIMIZE)[-1]
    assert note.author == SYSTEM and note.kind == MessageKind.EVENT
    with pytest.raises(ValueError):
        actions.switch_mode(v, "m1", LeadMode.OPTIMIZE)
    with pytest.raises(PermissionError):
        actions.switch_mode(v, "outsider", LeadMode.LAUNCH)


def test_bottleneck_suggestion_and_when_optimize_is_complete():
    v = campus()
    assert modes.suggest_bottleneck(v) is None
    for lens, rung in (("problem", Rung.SAID), ("business_model", Rung.SAID), ("customer", Rung.DID)):
        records.grade_lens(v, lens, rung, "", "", by=EIR)
    assert modes.suggest_bottleneck(v) == "problem"  # a tie on rung: the lens closer to the customer
    records.set_bottleneck(v, "business_model", "Nobody has paid yet, and the fee decides the model", by=EIR)
    assert not modes.optimize_complete(v)
    x = experiments.create(v, by=EIR, method="Offer prepaid listings to 10 sellers", lens="business_model",
                           supported_if="4 or more prepay", refuted_if="fewer than 4 prepay", method_rung=Rung.PAID)
    experiments.start(v, x.id, by="m1")
    experiments.record_result(v, x.id, "5 of 10 prepaid", by="m1")
    experiments.judge(v, x.id, "Supported", "5 is above the agreed 4", by=EIR)
    assert modes.optimize_complete(v)
