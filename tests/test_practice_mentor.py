"""Practice, stage 2, with a fake model (no network).

- The AI characters: a new customer each time; each character sees only what its kind allows.
- The practice coach's feedback and hints.
- The lead mentor's side:
  - feedback a member sends;
  - the source guard that keeps practice out of the evidence;
  - suggested practice sessions.
"""
import pytest

from eir import actions, changes, memory, practice
from eir.coach.ai import AICoach
from eir.coach.base import LeadEvent
from eir.coach.scripted import ScriptedCoach
from eir.filestore import MemoryFileStore
from eir.llm import ToolCall, ToolRun
from eir.models import EIR, SYSTEM, Rung
from eir.seed import demo_ventures, practice_script_for
from eir.tools import ToolBox


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


def prepared(vid, character, scenario):
    return [line.text for line in practice_script_for(vid, character, scenario).lines]


def finished(v, character, scenario, share=False):
    """A demo session played with its prepared lines and ended; optionally sent to the mentor (without a reply)."""
    coach = ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", character, scenario)
    for text in prepared(v.id, character, scenario):
        actions.practice_message(v, coach, r.id, "m1", text)
    actions.end_practice(v, coach, r.id, "m1")
    if share:
        practice.share(r, by="m1")
    return r


class FakeLLM:
    """Planned model answers: `texts` for chat and the mentor's reply, `data` for chat_json, in order (the last one
    repeats), and `plan` for the lead mentor's tool calls. Records what it was asked."""

    class cfg:
        model_name = "fake-model"

    def __init__(self, texts=("Okay.",), data=({},), plan=(), fail=False):
        self.texts, self.data, self.plan, self.fail = list(texts), list(data), list(plan), fail
        self.chats, self.jsons, self.runs, self.results = [], [], [], []

    @staticmethod
    def _next(items):
        return items.pop(0) if len(items) > 1 else items[0]

    def chat(self, system, messages, max_tokens=1200):
        if self.fail:
            raise RuntimeError("the endpoint timed out")
        self.chats.append((system, messages))
        return self._next(self.texts)

    def chat_json(self, system, prompt):
        if self.fail:
            raise RuntimeError("the endpoint timed out")
        self.jsons.append((system, prompt))
        return self._next(self.data)

    def run_tools(self, system, messages, tools, handler, max_rounds=4):
        self.runs.append((system, messages, [t.name for t in tools]))
        self.results = [handler(ToolCall(f"c{i}", name, args)) for i, (name, args) in enumerate(self.plan)]
        return ToolRun(self._next(self.texts), [], "native")


# ---- the AI characters ----
def test_the_ai_customer_is_a_new_person_who_knows_nothing_about_the_idea():
    v = venture()
    llm = FakeLLM(data=[{"persona": "Jordan, a sophomore moving out of a double room",
                         "profile": "Jordan left a desk lamp behind last May."}, {"persona": "Ana, a senior"}],
                  texts=["Jordan: Last May I just left the lamp in the hallway.\n[[WRAP_UP]]"])
    coach = AICoach(llm)
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    assert r.persona.startswith("Jordan") and r.messages[0].text.startswith("Hi, I'm Jordan.")
    assert practice.segment(v) in llm.jsons[0][1] and "Campus Loop" not in llm.jsons[0][1]
    reply = actions.practice_message(v, coach, r.id, "m1", "Tell me about the last time you moved out.")
    assert reply.text == "Last May I just left the lamp in the hallway." and r.wrapped_up
    system, messages = llm.chats[-1]
    assert "Jordan, a sophomore" in system and "Jordan left a desk lamp" in system and "[[WRAP_UP]]" in system
    for secret in ("Campus Loop", "$3", "Residence Life", v.hypotheses[1].statement):
        assert secret not in system
    assert messages[1] == {"role": "assistant", "content": r.messages[0].text}
    assert messages[-1] == {"role": "user", "content": "Alice: Tell me about the last time you moved out."}
    actions.start_practice(v, coach, "m2", "customer", "discovery")
    assert "other than: Jordan." in llm.jsons[-1][1]  # a new person each time


def test_without_a_persona_from_the_model_the_scripted_customer_steps_in():
    r = actions.start_practice(venture(), AICoach(FakeLLM(data=[{}])), "m1", "customer", "discovery")
    assert r.persona.startswith("Maya")  # Campus Loop's prepared customer
    luma = venture("V-LUMA")
    r = actions.start_practice(luma, AICoach(FakeLLM(fail=True)), "m1", "customer", "discovery")
    assert practice.first_name(r) in practice.NAMES


def test_the_ai_judge_asks_its_own_first_question_from_the_submission_and_knows_the_timing():
    v, store = venture(), MemoryFileStore()
    actions.upload_file(v, ScriptedCoach(), store, "m1", "Pitch deck.md", b"# Campus Loop\nSlide 2: movers left items.", "")
    llm = FakeLLM(texts=["Who pays: the mover or the student moving in?"])
    q = actions.start_practice(v, AICoach(llm), "m1", "judge", "qa", file_ids=(v.files[-1].id,), files=store)
    assert q.messages[0].text == ("I've read your material, so let's go straight to questions. Who pays: the mover "
                                  "or the student moving in?")
    system = llm.chats[0][0]
    assert "VENTURE: Campus Loop" in system and "Slide 2: movers left items." in system
    assert "Mark Ain Business Plan Competition" in system and "KEY-QUESTION ANSWERS" not in system
    llm = FakeLLM(texts=["That ran long. Who exactly is your first customer?"])
    p = actions.start_practice(v, AICoach(llm), "m1", "judge", "pitch")
    actions.practice_message(v, AICoach(llm), p.id, "m1", " ".join(["word"] * 500))
    assert "500 words ≈ 3:34 (target 3:00): over the limit." in llm.chats[-1][0]


def test_the_ai_challenger_reads_the_records_and_falls_back_to_the_prepared_first_question():
    v = venture()
    llm = FakeLLM(texts=["Who exactly is the buyer?"])
    r = actions.start_practice(v, AICoach(llm), "m1", "challenger", "holes")
    assert r.messages[0].text.endswith("Who exactly is the buyer?")
    assert "2 of 3 interviewees said they would only use it if it is free" in llm.chats[0][0]
    r = actions.start_practice(v, AICoach(FakeLLM(fail=True)), "m1", "challenger", "holes")
    assert practice_script_for("V-CAMPUS", "challenger", "holes").first in r.messages[0].text


# ---- the practice coach ----
def test_the_coach_writes_the_feedback_and_the_apps_own_check_is_kept():
    v = venture()
    data = {"scores": {"honesty": 4, "evidence": "2", "consistency": 9, "made_up": 1},  # clarity is missing
            "verdict": "Honest, but light on evidence.", "strengths": ["a", "b", "c"], "fixes": ["f1", "f2", "f3", "f4"],
            "tough_questions": ["\"Who pays?\" → The buyer fee is untested."], "problems": ["p1"], "checks": ["c1"],
            "unsupported_claims": []}
    llm = FakeLLM(texts=["Which is it?"], data=[data])
    coach = AICoach(llm)
    r = actions.start_practice(v, coach, "m1", "challenger", "holes")
    actions.practice_message(v, coach, r.id, "m1", "We already have 40 pre-orders.")
    fb = actions.end_practice(v, coach, r.id, "m1")
    plain = practice.plain_feedback(v, r)
    assert fb.scores == {"honesty": 4, "evidence": 2, "consistency": 5, "clarity": plain.scores["clarity"]}
    assert fb.strengths == ["a", "b"] and fb.fixes == ["f1", "f2", "f3"] and fb.problems == ["p1"] and fb.checks == []
    assert not fb.simplified and any("don't show 40" in c for c in fb.unsupported_claims)
    prompt = llm.jsons[-1][1]
    assert "We already have 40 pre-orders." in prompt and "Offer prepaid $3 listings" in prompt
    assert '"honesty": <1-5>' in prompt and "Fill problems" in prompt


def test_a_customer_feedback_keeps_its_own_lists_and_a_coach_without_scores_falls_back():
    v = venture()
    coach = AICoach(FakeLLM(texts=["Maybe."], data=[{"persona": "Sam, a junior", "profile": "Sam moved out."},
                                                     {"scores": {"past": 2}, "checks": ["k1"], "problems": ["no"],
                                                      "unsupported_claims": ["no"]}]))
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    actions.practice_message(v, coach, r.id, "m1", "Would you pay $3?")
    fb = actions.end_practice(v, coach, r.id, "m1")
    assert fb.checks == ["k1"] and fb.problems == [] and fb.unsupported_claims == [] and fb.scores["past"] == 2
    assert set(fb.scores) == {d.id for d in practice.spec("customer").rubric}
    r = actions.start_practice(v, ScriptedCoach(), "m1", "customer", "discovery")
    actions.practice_message(v, ScriptedCoach(), r.id, "m1", "Tell me about the last time.")
    assert actions.end_practice(v, AICoach(FakeLLM(data=[{"verdict": "no scores"}])), r.id, "m1").simplified


def test_the_ai_hint_is_one_line_from_the_records_and_the_character_never_sees_it():
    v = venture()
    llm = FakeLLM(data=[{"persona": "Sam, a junior", "profile": "Sam moved out."}],
                  texts=['"Ask when it last happened."', "Last spring."])
    coach = AICoach(llm)
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    hint = actions.practice_hint(v, coach, r.id, "m1")
    assert hint == "Ask when it last happened." and "Offer prepaid $3 listings" in llm.chats[-1][1][0]["content"]
    actions.practice_message(v, coach, r.id, "m1", "When did you last move out?")
    assert hint not in llm.chats[-1][0] and hint not in str(llm.chats[-1][1])


# ---- the lead mentor ----
def test_sent_feedback_becomes_a_task_and_the_answer_to_where_the_team_pitched():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "judge", "pitch")
    with pytest.raises(ValueError, match="End the session first"):
        actions.share_practice(v, coach, r.id, "m1")
    for text in prepared("V-CAMPUS", "judge", "pitch"):
        actions.practice_message(v, coach, r.id, "m1", text)
    actions.end_practice(v, coach, r.id, "m1")
    with pytest.raises(ValueError, match="one line"):
        actions.share_practice(v, coach, r.id, "m1", note="x" * 300)
    reply = actions.share_practice(v, coach, r.id, "m1", note="The money question froze me")
    note = v.conversation[-2]
    assert note.author == SYSTEM and note.rehearsal_id == r.id and note.event == f"practice:{r.id}"
    assert note.text == ("Alice sent the feedback from a practice session with the competition judge (3-minute pitch "
                         "+ questions) to the Virtual EIR.")
    assert reply.author == EIR and reply.rehearsal_id == r.id and len(reply.change_groups) == 2
    assert "The money question froze me" in reply.text and "not evidence" in reply.text
    task = v.next_steps[-1]
    assert task.text.startswith("From practice: Replace") and task.source == f"practice:{r.id}"
    answer = v.answer("pd_practice")
    assert answer.rung == Rung.ASSERTION and "AI competition judge" in answer.text
    assert "What have customers actually done so far?" in answer.text
    changes.undo_group(v, reply.change_groups[0], "m1")
    assert task.id not in [s.id for s in v.next_steps]
    with pytest.raises(ValueError, match="already sent"):
        actions.share_practice(v, coach, r.id, "m1")


def test_a_failed_reply_keeps_the_feedback_sent_and_can_be_asked_again():
    class Failing(ScriptedCoach):
        def lead_turn(self, v, box, event=None):
            raise RuntimeError("the endpoint timed out")

    v = venture()
    r = finished(v, "challenger", "holes")
    with pytest.raises(RuntimeError):
        actions.share_practice(v, Failing(), r.id, "m2")
    assert r.shared_at and r.shared_by == "m2" and actions.pending_event(v) == LeadEvent("practice", r.id)
    assert actions.awaiting_reply(v) and not v.changes
    reply = actions.retry_reply(v, ScriptedCoach(), "m2")
    assert reply.rehearsal_id == r.id and not actions.awaiting_reply(v)
    assert v.answer("pd_practice").rung == Rung.NONE  # a challenger session doesn't say where the team pitched


def test_practice_is_not_evidence():
    v = venture()
    judge, challenger = finished(v, "judge", "pitch", share=True), finished(v, "challenger", "holes", share=True)
    kept = finished(v, "customer", "discovery")  # not sent
    box, source = ToolBox(v), f"practice:{judge.id}"
    allowed = [("add_task", {"text": "Rewrite the waitlist line", "source": source}),
               ("add_assumption", {"statement": "Buyers will pay a $1 pickup fee", "importance": 3, "source": source}),
               ("set_focus", {"text": "Who pays?", "kind": "assumption", "ref": "H2", "source": source}),
               ("record_answer", {"question_id": "pd_practice", "text": "Pitched to the AI judge", "rung": 4,
                                  "source": source})]
    for name, args in allowed:
        assert not box.call(ToolCall(name, name, args)).startswith("ERROR"), name
    assert v.answer("pd_practice").rung == Rung.ASSERTION  # the team's own account, whatever rung was asked for
    refused = [("add_evidence", {"assumption_id": "H2", "text": "The judge liked the fee", "direction": "for",
                                 "rung": 3, "source": source}),
               ("update_canvas", {"block": "Revenue Streams", "text": "$3 fee", "rung": 3, "source": source}),
               ("record_answer", {"question_id": "pd_commitment", "text": "40 pre-orders", "rung": 5, "source": source}),
               ("complete_task", {"task_id": "S1", "source": source}),
               ("update_assumption", {"assumption_id": "H2", "statement": "Sellers pay", "source": source}),
               ("record_answer", {"question_id": "pd_practice", "text": "Challenged", "rung": 1,
                                  "source": f"practice:{challenger.id}"}),
               ("add_task", {"text": "x", "source": f"practice:{kept.id}"}),
               ("add_task", {"text": "x", "source": "practice:R-nope"})]
    before = len(v.changes)
    results = [box.call(ToolCall(name, name, args)) for name, args in refused]
    assert all(r.startswith("ERROR") for r in results), results
    assert "practice is not evidence" in results[0] and "only a session with the judge" in results[5]
    assert "sent you no practice feedback" in results[6] and len(v.changes) == before


def test_the_mentor_can_suggest_a_practice_session():
    v, coach = venture(), ScriptedCoach()
    box = ToolBox(v)
    for args in ({"character": "investor", "scenario": "pitch"}, {"character": "judge", "scenario": "holes"},
                 {"character": "challenger", "scenario": "assumption"}):
        assert box.call(ToolCall("p", "suggest_practice", {**args, "reason": "x"})).startswith("ERROR")
    box.call(ToolCall("p", "suggest_practice", {"character": "challenger", "scenario": "assumption",
                                                "assumption_id": "H2", "reason": "x"}))
    assert box.suggested_practice == "challenger/assumption/H2" and not box.groups  # no record changes
    assert practice.parse_suggestion(v, box.suggested_practice).label == "Practise with the challenger: Attack one assumption"
    assert practice.parse_suggestion(v, "judge/karaoke") is None and practice.parse_suggestion(v, "") is None
    box.rollback()
    assert box.suggested_practice == ""
    line = next(t for t in coach.suggestions(v, "m1") if "Foundry Friday" in t)
    reply = actions.mentor_message(v, coach, "m1", line)
    assert reply.practice_suggestion == "judge/pitch" and not reply.change_groups
    reply = actions.mentor_message(v, coach, "m2", "Can we rehearse our customer interviews first?")
    assert reply.practice_suggestion == "customer/discovery" and "button" in reply.text


def test_the_mentor_sees_only_sent_feedback_never_the_conversation():
    v = venture()
    sent, kept = finished(v, "judge", "pitch", share=True), finished(v, "challenger", "holes")
    context = memory.lead_context(v)
    assert f"(practice:{sent.id})" in context and sent.feedback.verdict in context
    assert kept.feedback.verdict not in context and f"practice:{kept.id}" not in context
    assert all(m.text not in context for m in sent.messages)
    assert "- judge/pitch: Competition judge, 3-minute pitch + questions." in context


def test_the_ai_mentor_is_told_what_to_do_with_practice_feedback():
    v = venture()
    r = finished(v, "judge", "pitch")
    llm = FakeLLM(texts=["Name the milestone the money buys."],
                  plan=[("add_task", {"text": "Rewrite the ask", "source": f"practice:{r.id}"}),
                        ("add_evidence", {"assumption_id": "H2", "text": "The judge doubted the fee", "direction":
                                          "against", "rung": 3, "source": f"practice:{r.id}"})])
    reply = actions.share_practice(v, AICoach(llm), r.id, "m1")
    system, messages, tools = llm.runs[-1]
    assert "suggest_practice" in tools and "PRACTICE FEEDBACK THE TEAM SENT YOU" in system and "PRACTICE:" in system
    note = messages[-1]["content"]
    assert f"practice:{r.id}" in note and "practice is not evidence" in note and "pd_practice (rung 1)" in note
    assert llm.results[0].startswith("Task") and llm.results[1].startswith("ERROR")
    assert reply.rehearsal_id == r.id and len(reply.change_groups) == 1
