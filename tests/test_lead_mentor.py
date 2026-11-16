"""Talking to the lead mentor: every message gets a reply, record updates are linked to the reply and can be undone,
a failed turn rolls back, consultations stay private, and the scripted mentor keeps the keyless demo working."""
from datetime import datetime, timedelta, timezone

import pytest

from eir import actions, memory
from eir.coach.ai import AICoach
from eir.coach.base import LeadEvent
from eir.coach.scripted import ScriptedCoach
from eir.llm import ToolCall, ToolRun
from eir.models import (EIR, ConsultationSummary, Direction, ExperimentStatus, HypothesisStatus, LeadMode, Message,
                        Rung, StepStatus)
from eir.seed import demo_ventures


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


class FakeLLM:
    """Plays planned tool calls through the real ToolBox and returns a fixed reply."""

    class cfg:
        model_name = "fake-model"

    def __init__(self, plan=(), text="Noted.", fail=False):
        self.plan, self.text, self.fail, self.seen, self.results = list(plan), text, fail, [], []

    def run_tools(self, system, messages, tools, handler, max_rounds=4):
        self.seen.append((system, messages, [t.name for t in tools]))
        self.results = [handler(ToolCall(f"c{i}", name, args)) for i, (name, args) in enumerate(self.plan)]
        if self.fail:
            raise RuntimeError("the endpoint timed out")
        return ToolRun(self.text, [], "native")

    def chat(self, system, messages, max_tokens=1200):
        return "Bob reported interviews; the team agreed to test the fee."

    def chat_json(self, system, prompt):
        return {}


def test_every_message_gets_a_reply_and_its_updates_can_be_undone():
    v = venture()
    llm = FakeLLM([("add_evidence", {"assumption_id": "H2", "text": "4 of 5 want it free", "direction": "against",
                                     "rung": 3, "source": "m1"}),
                   ("set_focus", {"text": "Who pays: sellers or buyers?", "kind": "assumption", "ref": "H2",
                                  "source": "m1"})],
                  text="Thanks Bob. Recorded: evidence against H2.")
    reply = actions.mentor_message(v, AICoach(llm), "m2", "4 of 5 interviewees said they'd only use it if free")
    assert reply.author == EIR and reply.text.startswith("Thanks Bob") and len(reply.change_groups) == 2
    assert all(not r.startswith("ERROR") for r in llm.results)
    system, messages, tools = llm.seen[0]
    assert messages[-1]["content"].startswith("[m1] Bob: 4 of 5")
    assert "KEY QUESTIONS" in system and "CANVAS" in system and "record_answer" in tools
    actions.undo(v, reply.change_groups[0], "m2")
    assert len(v.hypothesis("H2").evidence_items) == 2


def test_a_failed_turn_rolls_back_and_keeps_the_members_message():
    v = venture()
    llm = FakeLLM([("add_assumption", {"statement": "Buyers pay instead", "importance": 3, "source": "m1"})],
                  fail=True)
    with pytest.raises(RuntimeError):
        actions.mentor_message(v, AICoach(llm), "m1", "Maybe buyers should pay?")
    assert v.conversation[-1].author == "m1" and v.hypothesis("H4") is None and not v.changes


def test_the_lead_mentor_never_sees_a_consultation_transcript():
    v = venture()
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief", EIR)
    actions.consult_post(v, c.id, "m1", "Our secret supplier is Bob's uncle")
    llm = FakeLLM()
    actions.mentor_message(v, AICoach(llm), "m1", "Anything new?")
    system, messages, _ = llm.seen[0]
    assert "secret supplier" not in system + str(messages)
    assert "OPEN CONSULTATIONS" in system and "Is $3 supported?" in system


def test_the_optimize_mentor_gets_its_own_prompt_and_actions():
    v = venture()
    actions.switch_mode(v, "m1", LeadMode.OPTIMIZE)
    llm = FakeLLM()
    actions.mentor_message(v, AICoach(llm), "m1", "We have some paying sellers")
    system, _, tools = llm.seen[0]
    assert "OPTIMIZE MENTOR" in system and "LENSES" in system and "ENTRY CHECK" in system
    assert "grade_lens" in tools and "update_canvas" not in tools


def test_scripted_line_runs_its_actions():
    v = venture()
    reply = actions.mentor_message(v, ScriptedCoach(), "m2",
                                   "I did 2 more interviews. 4 of 5 total said they'd only use it if it's free.")
    assert v.step("S1").status == StepStatus.DONE
    assert v.hypothesis("H2").evidence_items[-1].direction == Direction.AGAINST
    assert v.hypothesis("H4").statement.startswith("Buyers")
    assert len(reply.change_groups) == 3


def test_scripted_mentor_keeps_topics_apart_and_opens_consultations():
    v = venture()
    reply = actions.mentor_message(v, ScriptedCoach(), "m1", "Can we get a pricing expert to look at the $3 fee?")
    assert reply.consultation_id and v.open_consultation("pricing")
    groups_before = len(v.changes)
    reply = actions.mentor_message(v, ScriptedCoach(), "m1", "So what price should we charge per item?")
    assert "consultant is working on with you" in reply.text and len(v.changes) == groups_before


def test_scripted_optimize_mentor_opens_with_the_evidence_check():
    v = venture()
    actions.switch_mode(v, "m1", LeadMode.OPTIMIZE)
    reply = actions.mentor_message(v, ScriptedCoach(), "m1", "Help us grow faster")
    assert "Launch Virtual EIR" in reply.text and reply.suggested_mode == LeadMode.LAUNCH


def test_scripted_judgment_against_the_agreed_criteria():
    v = venture()
    actions.start_experiment(v, "X-fee", "m1")
    actions.record_experiment_result(v, "X-fee", "m1", "2 of 10 movers prepaid")
    reply = actions.mentor_event(v, ScriptedCoach(), "m1", LeadEvent("judge", "X-fee"))
    x, h = v.experiment("X-fee"), v.hypothesis("H2")
    assert x.status == ExperimentStatus.CONCLUDED and h.status == HypothesisStatus.REFUTED
    assert h.rung == Rung.PAID and "Refuted" in reply.text and reply.change_groups


def test_a_returned_summary_becomes_tasks_the_team_can_undo():
    v = venture()
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief", EIR)
    actions.end_consultation(v, c.id, "m1", ConsultationSummary(conclusions=["Free is the real competitor"],
                                                                suggested_todos=["Offer buyers a $1 pickup fee"]))
    reply = actions.mentor_event(v, ScriptedCoach(), "m1", LeadEvent("summary", c.id),
                                 note="Alice sent the Pricing & business model consultant's summary to the mentor.")
    assert v.next_steps[-1].text == "Offer buyers a $1 pickup fee" and reply.consultation_id == c.id
    assert "Free is the real competitor" in reply.text
    actions.undo(v, reply.change_groups[0], "m1")
    assert v.next_steps[-1].text != "Offer buyers a $1 pickup fee"


def test_earlier_days_are_summarized_once_for_the_briefing():
    v = venture()
    when = datetime.now(timezone.utc) - timedelta(days=1)
    v.conversation.append(Message("m2", "We interviewed 2 more movers", created_at=when.isoformat(timespec="seconds")))
    llm = FakeLLM()
    actions.mentor_message(v, AICoach(llm), "m1", "Morning!")
    actions.mentor_message(v, AICoach(llm), "m1", "Second message today")
    days = [d for d in v.day_summaries if d.day == when.astimezone().date().isoformat()]
    assert len(days) == 1 and days[0].summary == "Bob reported interviews; the team agreed to test the fee."
    assert any(line.startswith(f"**Last time ({days[0].label}):**") for line in memory.briefing(v))


def test_the_briefing_answers_what_to_do_now():
    lines = memory.briefing(venture())
    assert lines[0].startswith("**Current focus:** Will sellers really pay $3 per item?")
    assert lines[1].startswith("**Next:** Experiment (draft")
