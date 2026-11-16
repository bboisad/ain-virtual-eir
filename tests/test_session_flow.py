"""A coaching session with the scripted mentor, without the UI."""
from eir import actions, brief, memory
from eir.coach.scripted import ScriptedCoach
from eir.models import EIR, HypothesisStatus, StepStatus
from eir.seed import demo_ventures


def campus():
    return next(v for v in demo_ventures() if v.name == "Campus Loop")


def test_the_briefing_starts_from_the_focus_and_last_time():
    lines = memory.briefing(campus())
    assert lines[0].startswith("**Current focus:**") and any(line.startswith("**Last time (Oct 5):**")
                                                              for line in lines)


def test_suggestions_depend_on_speaker_and_carry_no_mention():
    v, coach = campus(), ScriptedCoach()
    bob = coach.suggestions(v, "m2")
    assert any("2 more interviews" in s for s in bob) and not any(s.startswith("@") for s in bob)
    assert not any("I'm sure they'll pay" in s for s in bob)  # Alice's line


def test_a_session_updates_the_records_and_the_next_briefing():
    v, coach = campus(), ScriptedCoach()
    line = next(s for s in coach.suggestions(v, "m2") if "2 more interviews" in s)
    actions.mentor_message(v, coach, "m2", line)
    actions.mentor_message(v, coach, "m1", "Can we talk to a real mentor about pricing and liability for stored items?")
    assert v.handoff
    assert v.step("S1").status == StepStatus.DONE and len(v.hypotheses) == 4
    assert [m.author for m in v.conversation] == ["m2", EIR, "m1", EIR]
    assert line not in coach.suggestions(v, "m2")  # a used line is not suggested again


def test_disagreement_closes_when_hypothesis_resolved():
    v = campus()
    v.hypothesis("H2").status = HypothesisStatus.REFUTED
    assert v.open_disagreements() == []


def test_free_text_gets_a_grounded_fallback_reply():
    v, coach = campus(), ScriptedCoach()
    reply = actions.mentor_message(v, coach, "m3", "We think it's fine.")
    assert "Carol" in reply.text and "still open" in reply.text and not reply.change_groups


def test_mentor_brief():
    v = campus()
    text = brief.mentor_brief(v, "Pricing")
    assert "Evidence so far" in text and "Residence Life" in text and "Experiments under way" in text
    actions.share_brief(v, "Pricing", text, "m1")
    assert v.timeline[-1].kind.value == "brief" and v.shared_briefs and v.handoff is None
