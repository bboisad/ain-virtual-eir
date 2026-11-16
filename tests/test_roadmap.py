"""Foundry roadmap v0.2: key questions on the evidence ladder, the Virtual EIR's step judgment,
EIR calibration of the first judgments, graduation decided only by AIN EIRs, and the questioning engine."""
import pytest

from eir import access, actions, brief, memory, questioning, records, roadmap
from eir.access import Account, Role
from eir.coach.scripted import ScriptedCoach
from eir.models import EIR, Module, ReviewState, Rung, Verdict
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures

STAFF = Account("roberto", "AIN staff (demo)", Role.STAFF)
FOUNDER = Account("alice", "Alice Chen")


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


def answer(v, question_id, text, rung):
    """The mentor records an answer with its grade (as its record_answer action does)."""
    records.record_answer(v, question_id, text, rung, "", by=EIR)


def answer_all(v, deliverable_id):
    for q in roadmap.deliverable(deliverable_id).questions:
        answer(v, q.id, f"Recorded evidence for {q.id}", q.need)


def test_answer_needs_text_and_a_team_member():
    v = campus()
    with pytest.raises(ValueError):
        actions.submit_answer(v, ScriptedCoach(), "pd_legal", "  ", "m1")
    with pytest.raises(PermissionError):
        actions.submit_answer(v, ScriptedCoach(), "pd_legal", "LLC", "stranger")
    actions.submit_answer(v, ScriptedCoach(), "pd_legal", "LLC, advised by the law clinic", "m3")
    a = v.answer("pd_legal")
    assert a.rung == Rung.ASSERTION and "Carol" in a.source


def test_not_yet_lists_each_gap_with_its_evidence_level():
    v = campus()
    j = actions.check_step(v, "pitch_deck", "m1")
    assert j.verdict == Verdict.NOT_YET and "pitch_deck" not in v.done and v.module == Module.M2
    assert any("Has anyone paid" in r and "you have 1 · Assertion" in r for r in j.reasons)
    assert j.review == ReviewState.NONE and len(j.consider) == 1


def test_ready_advances_and_first_judgments_go_to_an_eir():
    v = campus()  # seed: two READY judgments already confirmed by an EIR
    answer_all(v, "pitch_deck")
    j = actions.check_step(v, "pitch_deck", "m1")
    assert j.verdict == Verdict.READY and j.review == ReviewState.PENDING  # 3rd READY: still calibrating
    assert len(j.consider) >= 3 and v.module == Module.M3 and "pitch_deck" in v.done
    answer_all(v, "business_plan")
    j4 = actions.check_step(v, "business_plan", "m1")
    assert j4.verdict == Verdict.READY and j4.review == ReviewState.NONE  # calibration over
    assert v.module == Module.M3  # never moves to NextCorps by itself
    with pytest.raises(ValueError):
        actions.check_step(v, "customer_discovery", "m1")  # only the current module


def test_eir_confirms_or_reopens_a_judgment():
    v = campus()
    answer_all(v, "pitch_deck")
    actions.check_step(v, "pitch_deck", "m1")
    [(i, _)] = access.judgments_for_staff(STAFF, v)
    with pytest.raises(PermissionError):
        access.review_judgment(FOUNDER, v, i, confirm=True)
    with pytest.raises(ValueError):
        access.review_judgment(STAFF, v, i, confirm=False, note="")
    j = access.review_judgment(STAFF, v, i, confirm=False, note="Pre-orders from friends do not count")
    assert j.review == ReviewState.REOPENED and v.module == Module.M2 and "pitch_deck" not in v.done
    assert "Pre-orders from friends" in v.timeline[-1].text
    assert access.judgments_for_staff(STAFF, v) == []


def test_graduation_is_decided_only_by_ain_eirs():
    v = campus()
    with pytest.raises(ValueError):
        actions.request_graduation(v, "m1")
    for d in ("pitch_deck", "business_plan"):
        answer_all(v, d)
        actions.check_step(v, d, "m1")
    actions.request_graduation(v, "m1")
    assert access.staff_directory(STAFF, InMemoryRepository([v]))[0].graduation_requested
    with pytest.raises(PermissionError):
        access.graduation_packet(FOUNDER, v)
    with pytest.raises(PermissionError):
        access.decide_graduation(FOUNDER, v, approve=True)
    assert "Graduation review: Campus Loop" in access.graduation_packet(STAFF, v)
    with pytest.raises(ValueError):
        access.decide_graduation(STAFF, v, approve=False, note="")
    access.decide_graduation(STAFF, v, approve=False, note="Show retention")
    assert v.graduation == "returned: Show retention" and v.module == Module.M3
    actions.request_graduation(v, "m1")
    access.decide_graduation(STAFF, v, approve=True)
    assert v.module == Module.ALUMNI


def test_step_back_is_logged_with_a_reason():
    v = campus()
    with pytest.raises(ValueError):
        actions.step_back(v, "m2", "")
    assert actions.step_back(v, "m2", "0 of 10 students paid the fee") == Module.M1
    assert "0 of 10 students paid" in v.timeline[-1].text and v.done == []


def test_questioning_presses_the_weakest_claim_up_the_chain():
    v = campus()
    q = questioning.next_question(v)
    assert "Has anyone paid" in q and "How do you know?" in q and "..\"" not in q
    answer(v, "pd_commitment", "12 students said they would pay", Rung.SAID)
    answer(v, "pd_dmu", "Movers decide; RAs can block", Rung.SAID)
    q = questioning.next_question(v)
    assert "Has anyone paid" in q and "actually do something" in q and "prove you wrong" in q
    answer_all(v, "pitch_deck")
    assert "Check this step" in questioning.next_question(v)


def test_the_mentor_presses_claims_and_never_advances():
    v = campus()
    ctx = memory.lead_context(v)
    assert "M2 · The Perfect Pitch" in ctx and "QUESTION CHAIN" in ctx and "Never say a step is complete" in ctx
    actions.mentor_message(v, ScriptedCoach(), "m1", "what next?")
    assert v.module == Module.M2 and "pitch_deck" not in v.done


def test_brief_and_staff_directory_show_the_roadmap():
    v = campus()
    text = brief.mentor_brief(v, "Preparing our next EIR Foundry session")
    assert "Roadmap checklist" in text and "Pitch deck" in text and "Next EIR session:** 2026-10-23" in text
    entry = access.staff_directory(STAFF, InMemoryRepository([v]))[0]
    assert entry.module == "M2 · The Perfect Pitch" and entry.reviews_pending == 0


def test_learning_log_and_profile_are_the_students_own():
    v = campus()
    with pytest.raises(ValueError):
        actions.add_learning(v, " ", "m1")
    actions.add_learning(v, "Saying yes is not paying", "m2")
    assert v.learning_log[-1].text == "Saying yes is not paying"
    with pytest.raises(PermissionError):
        actions.set_experience(v, "m2", "Founded a startup before", "m1")
    actions.set_experience(v, "m1", "Founded a startup before", "m1")
    assert v.member("m1").experience == "Founded a startup before"


def test_resources_follow_module_and_venture_type():
    v = campus()
    names = [r.name for r in roadmap.resources(v, limit=20)]
    assert "Foundry Friday: pitch practice" in names and not any("UR Ventures" in n for n in names)
    luma = next(x for x in demo_ventures() if x.id == "V-LUMA")
    assert any("UR Ventures" in r.name for r in roadmap.resources(luma, limit=20))
    assert roadmap.expertise_for("IP or regulatory expertise") == "Research commercialization and IP"


def test_the_virtual_eir_grades_evidence_not_the_student():
    from eir import grading
    assert grading.grade("Alice believes students will pay $3").rung == Rung.ASSERTION
    assert grading.grade("According to a Census report, 40% of students move each May").rung == Rung.SECONDARY
    assert grading.grade("We interviewed 12 movers; 9 said they would pay").rung == Rung.SAID
    assert grading.grade("We interviewed movers").rung == Rung.SECONDARY  # not specific: how many?
    assert grading.grade("15 students signed up for the waitlist").rung == Rung.DID
    assert grading.grade("6 students pre-ordered at $3").rung == Rung.PAID
    assert grading.grade("4 of 6 reordered the next month").rung == Rung.RETAINED
    v = campus()
    rung = actions.submit_answer(v, ScriptedCoach(), "pd_commitment", "15 students signed up for the waitlist", "m1")
    a = v.answer("pd_commitment")
    assert rung == Rung.DID and a.why and "Alice" in a.source
    assert v.changes[-1].by == "m1" and "level 1 → 4" in v.changes[-1].summary  # listed under Recent changes
