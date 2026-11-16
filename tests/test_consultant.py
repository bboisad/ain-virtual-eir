"""A consultation from start to finish (design decision 1): the lead mentor brings a consultant in with a brief, the
student talks to the consultant, the consultant proposes to end, the student previews the summary and adds one line,
and the lead mentor acts on it. Failures keep the student's words and can be retried."""
import pytest

from eir import actions, changes, consult
from eir.coach.ai import AICoach
from eir.coach.base import LeadEvent, LeadTurn
from eir.coach.scripted import ScriptedCoach
from eir.models import CONSULTANT, EIR, ConsultationStatus, Message
from eir.seed import consult_script_for, demo_ventures


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


def lines(vid, consultant):
    return [line.text for line in consult_script_for(vid, consultant).lines]


class Flaky(ScriptedCoach):
    """The scripted coach, failing the next n consultant turns or lead turns like a dropped connection."""

    def __init__(self, consult_fail=0, lead_fail=0, lead_text=None):
        super().__init__()
        self.consult_fail, self.lead_fail, self.lead_text = consult_fail, lead_fail, lead_text

    def consult_turn(self, v, c):
        if self.consult_fail:
            self.consult_fail -= 1
            raise RuntimeError("the endpoint timed out")
        return super().consult_turn(v, c)

    def lead_turn(self, v, box, event=None):
        if self.lead_fail:
            self.lead_fail -= 1
            raise RuntimeError("the endpoint timed out")
        if self.lead_text is not None:
            return LeadTurn(self.lead_text)  # replies without bringing anyone in
        return super().lead_turn(v, box, event)


# ---- opening ----
def test_a_click_in_the_rail_brings_the_consultant_in_with_the_mentors_brief():
    v, coach = venture(), ScriptedCoach()
    c, standard = actions.request_consultant(v, coach, "m1", "pricing")
    assert not standard and c.status == ConsultationStatus.OPEN and c.requested_by == EIR
    note, reply = v.conversation[-2:]
    assert note.text == "Alice asked the Virtual EIR to bring in the Pricing & business model consultant."
    assert reply.author == EIR and reply.consultation_id == c.id
    opening = c.messages[0]
    assert opening.author == CONSULTANT and "an AI, not a real person" in opening.text
    assert c.question in opening.text and consult.spec("pricing").checklist[0] in opening.text
    assert actions.request_consultant(v, coach, "m1", "pricing") == (c, False)  # one open per consultant


def test_without_a_brief_from_the_mentor_the_standard_brief_keeps_the_team_going():
    v = venture()
    c, standard = actions.request_consultant(v, Flaky(lead_text="Let's first look at your interviews."), "m2",
                                             "strategy")
    assert standard and c.requested_by == "m2" and c.brief.startswith("Question: Strategy & competition")
    v = venture()
    c, standard = actions.request_consultant(v, Flaky(lead_fail=1), "m2", "funding")
    assert standard and c.status == ConsultationStatus.OPEN
    assert not actions.awaiting_reply(v)  # answered by the standard brief: nothing to ask the mentor again


# ---- talking to the consultant ----
def test_every_message_gets_a_reply_and_a_failed_reply_keeps_the_message():
    v = venture()
    c, _ = actions.request_consultant(v, ScriptedCoach(), "m1", "pricing")
    coach = Flaky(consult_fail=1)
    with pytest.raises(RuntimeError):
        actions.consult_message(v, coach, c.id, "m1", "We never asked anyone about price.")
    assert c.messages[-1].author == "m1" and consult.awaiting_reply(c)
    reply = actions.consult_retry(v, coach, c.id, "m1")
    assert reply.author == CONSULTANT and not consult.awaiting_reply(c)
    with pytest.raises(PermissionError):
        actions.consult_message(v, coach, c.id, "outsider", "hi")


def test_the_scripted_consultant_stays_in_scope_and_hands_off_what_needs_a_human():
    v, coach = venture(), ScriptedCoach()
    c, _ = actions.request_consultant(v, coach, "m1", "funding")
    reply = actions.consult_message(v, coach, c.id, "m1", "An angel sent us a term sheet. Is it fair?")
    assert "decision for a human AIN EIR" in reply.text
    reply = actions.consult_message(v, coach, c.id, "m1", "Facebook Marketplace is a competitor; how are we different?")
    assert "outside what I cover" in reply.text
    while not c.proposed_end:  # then it works through its checklist and proposes to end
        actions.consult_message(v, coach, c.id, "m1", "We are not sure yet.")
    assert "summary" in c.messages[-1].text


def test_prepared_lines_end_with_a_proposal_and_a_summary_to_preview():
    v, coach = venture(), ScriptedCoach()
    c, _ = actions.request_consultant(v, coach, "m1", "pricing")
    assert coach.consult_suggestions(v, c, "m1") == lines("V-CAMPUS", "pricing")
    for text in lines("V-CAMPUS", "pricing"):
        actions.consult_message(v, coach, c.id, "m1", text)
    assert c.proposed_end and coach.consult_suggestions(v, c, "m1") == []
    draft = actions.draft_summary(v, coach, c.id, "m1")
    assert draft.question == c.question and "hallway" in draft.conclusions[0] and len(draft.suggested_todos) == 2
    assert c.status == ConsultationStatus.OPEN and c.summary is None  # a preview sends nothing
    actions.consult_message(v, coach, c.id, "m1", "Wait, one more question about buyers.")
    assert c.draft is None and not c.proposed_end  # talking on discards the preview


# ---- sending the summary back ----
def test_the_summary_goes_back_with_the_students_note_and_the_mentor_acts_on_it():
    v, coach = venture(), ScriptedCoach()
    c, _ = actions.request_consultant(v, coach, "m1", "pricing")
    for text in lines("V-CAMPUS", "pricing"):
        actions.consult_message(v, coach, c.id, "m1", text)
    with pytest.raises(ValueError):
        actions.send_summary(v, coach, c.id, "m1")  # preview first
    actions.draft_summary(v, coach, c.id, "m1")
    with pytest.raises(ValueError):
        actions.send_summary(v, coach, c.id, "m1", note="x" * 300)
    assert c.status == ConsultationStatus.OPEN
    reply = actions.send_summary(v, coach, c.id, "m1", note="I still want to try $3 first")
    assert c.status == ConsultationStatus.DONE and c.summary.student_note == "I still want to try $3 first"
    assert v.conversation[-2].text.startswith("Alice sent the Pricing & business model consultant's summary")
    assert reply.consultation_id == c.id and "the hallway" in reply.text and len(reply.change_groups) == 2
    assert [s.text for s in v.next_steps[-2:]] == consult_script_for("V-CAMPUS", "pricing").summary.suggested_todos
    changes.undo_group(v, reply.change_groups[0], "m1")
    assert v.next_steps[-1].text.startswith("Ask Residence Life")
    assert consult.rail(v)[0].state == "done"


def test_a_failed_reply_to_the_summary_can_be_asked_again():
    v = venture()
    c, _ = actions.request_consultant(v, ScriptedCoach(), "m1", "pricing")
    actions.draft_summary(v, ScriptedCoach(), c.id, "m1")
    with pytest.raises(RuntimeError):
        actions.send_summary(v, Flaky(lead_fail=1), c.id, "m1")
    assert c.status == ConsultationStatus.DONE and actions.pending_event(v) == LeadEvent("summary", c.id)
    assert actions.awaiting_reply(v)
    reply = actions.retry_reply(v, ScriptedCoach(), "m1")
    assert reply.consultation_id == c.id and not actions.awaiting_reply(v)


def test_an_investment_offer_reaches_a_human_eir():
    v, coach = venture("V-LUMA"), ScriptedCoach()
    c, _ = actions.request_consultant(v, coach, "m1", "funding")
    for text in lines("V-LUMA", "funding"):
        actions.consult_message(v, coach, c.id, "m1", text)
    draft = actions.draft_summary(v, coach, c.id, "m1")
    assert draft.needs_human and draft.human_topic == "valuation and equity offer"
    actions.send_summary(v, coach, c.id, "m1")
    assert v.handoff  # the mentor flags it; the team can share a brief with a human EIR from the menu


# ---- the AI consultant (fake model, no network) ----
class FakeLLM:
    class cfg:
        model_name = "fake-model"

    def __init__(self, text="", data=None):
        self.text, self.data, self.seen = text, data or {}, []

    def chat(self, system, messages, max_tokens=1200):
        self.seen.append((system, messages))
        return self.text

    def chat_json(self, system, prompt):
        self.seen.append((system, prompt))
        return self.data


def test_the_ai_consultant_sees_its_brief_never_the_mentor_chat_and_can_propose_to_end():
    v = venture()
    v.conversation.append(Message("m1", "Mentor-only: Carol may leave the team", mentor=v.lead_mode))
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief: Alice believes $3; 2 of 3 want it free",
                                  EIR)
    llm = FakeLLM("Then test both prices, Alice.\n[[PROPOSE_END]]")
    reply = actions.consult_message(v, AICoach(llm), c.id, "m1", "What should we test?")
    system, messages = llm.seen[0]
    assert "Brief: Alice believes $3" in system and consult.spec("pricing").checklist[0] in system
    assert "Carol may leave" not in system + str(messages)
    assert messages[0]["role"] == "user" and messages[-1]["content"] == "Alice: What should we test?"
    assert reply.text == "Then test both prices, Alice." and c.proposed_end


def test_the_ai_summary_is_parsed_and_hand_off_topics_are_enforced():
    v = venture()
    c = actions.invite_consultant(v, "funding", "How much should we raise?", "Brief: an angel made an offer", EIR)
    actions.consult_post(v, c.id, "m1", "The angel sent a term sheet for 20%")
    data = {"conclusions": "Raise only what the pilot needs", "suggested_todos": ["a", "b", "c", "d"],
            "needs_human": False, "disagreements": None}
    draft = actions.draft_summary(v, AICoach(FakeLLM(data=data)), c.id, "m1")
    assert draft.conclusions == ["Raise only what the pilot needs"] and draft.suggested_todos == ["a", "b", "c"]
    assert draft.question == "How much should we raise?" and draft.disagreements == []
    assert draft.needs_human and draft.human_topic == "term sheet"  # whatever the model said
