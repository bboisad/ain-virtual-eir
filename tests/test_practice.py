"""Practice with AI characters (design 2026-11-07): a target customer, a competition judge and a challenger.

What must hold:
- Characters only know what their kind allows. The customer knows who they are, never the team's idea.
- Nothing in practice changes a record.
- The session is the team's own: the mentor, consultants and AIN staff never see it.
- Only the feedback, once a member sends it, reaches the mentor.
- Failures keep the student's words.
"""
import pytest

from eir import access, actions, memory, practice
from eir.access import Account, Role
from eir.coach.scripted import ScriptedCoach
from eir.filestore import MemoryFileStore
from eir.models import CHARACTER, Difficulty, LeadMode, Message, RehearsalFeedback, RehearsalStatus
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures, practice_script_for
from eir.serde import from_dict, to_dict


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


def prepared(vid, character, scenario):
    return [line.text for line in practice_script_for(vid, character, scenario).lines]


def play(v, coach, r, texts, by="m1"):
    for text in texts:
        actions.practice_message(v, coach, r.id, by, text)


class Flaky(ScriptedCoach):
    """The scripted coach, failing the next n character turns, or always failing the feedback and hints."""

    def __init__(self, turn_fail=0, broken=False):
        super().__init__()
        self.turn_fail, self.broken = turn_fail, broken

    def practice_turn(self, v, r, material=""):
        if self.turn_fail:
            self.turn_fail -= 1
            raise RuntimeError("the endpoint timed out")
        return super().practice_turn(v, r, material)

    def practice_start(self, v, r, material=""):
        if self.broken:
            raise RuntimeError("the endpoint timed out")
        return super().practice_start(v, r, material)

    def practice_feedback(self, v, r, material=""):
        if self.broken:
            raise RuntimeError("the endpoint timed out")
        return super().practice_feedback(v, r, material)

    def practice_hint(self, v, r, material=""):
        if self.broken:
            raise RuntimeError("the endpoint timed out")
        return super().practice_hint(v, r, material)


# ---- the characters (knowledge/practice.json) ----
def test_three_characters_with_scenarios_difficulties_and_a_rubric():
    assert [c.id for c in practice.characters()] == ["customer", "judge", "challenger"]
    assert [c.sees for c in practice.characters()] == [practice.SEGMENT, practice.SUBMISSION, practice.RECORDS]
    for c in practice.characters():
        assert c.scenarios and c.tips and c.knows and c.wrap_up
        assert {d for d, _ in c.difficulty} == set(Difficulty)
        assert all(d.good and d.fix for d in c.rubric)
    judge, challenger = practice.spec("judge"), practice.spec("challenger")
    assert judge.scenario("pitch").pitch_seconds == 180 and challenger.scenario("assumption").needs_assumption
    assert any("real person" in rule for c in practice.characters() for rule in c.never)
    with pytest.raises(ValueError):
        practice.spec("investor")


# ---- starting ----
def test_starting_checks_membership_and_the_settings():
    v, coach = venture(), ScriptedCoach()
    with pytest.raises(PermissionError):
        actions.start_practice(v, coach, "outsider", "judge", "pitch")
    with pytest.raises(ValueError):
        actions.start_practice(v, coach, "m1", "judge", "karaoke")
    with pytest.raises(ValueError, match="assumption"):
        actions.start_practice(v, coach, "m1", "challenger", "assumption")
    with pytest.raises(ValueError, match="no longer exists"):
        actions.start_practice(v, coach, "m1", "judge", "pitch", file_ids=("F-gone",))
    r = actions.start_practice(v, coach, "m1", "challenger", "assumption", Difficulty.TOUGH, assumption_id="H2")
    assert r.assumption_id == "H2" and r.difficulty == Difficulty.TOUGH and r.started_by == "m1"
    assert "Sellers will pay a $3 fee per item" in r.messages[0].text
    customer = actions.start_practice(v, coach, "m1", "customer", "discovery", file_ids=("F-notes",))
    assert customer.file_ids == []  # a customer knows only who they are
    assert v.rehearsals == [r, customer] and all(x.status == RehearsalStatus.OPEN for x in v.rehearsals)


def test_a_customer_is_a_made_up_person_from_the_segment():
    v, coach = venture(), ScriptedCoach()
    maya = actions.start_practice(v, coach, "m1", "customer", "discovery")
    assert maya.persona.startswith("Maya") and maya.persona_profile
    assert maya.messages[0].author == CHARACTER and maya.messages[0].text.startswith("Hi, I'm Maya.")
    assert practice.character_label(maya) == "Maya (target customer, AI)"
    luma = venture("V-LUMA")
    someone = actions.start_practice(luma, coach, "m1", "customer", "discovery")
    name = practice.first_name(someone)
    assert name in practice.NAMES and someone.messages[0].text.startswith(f"Hi, I'm {name}.")
    assert practice.segment(luma) in someone.persona_profile


def test_a_failed_start_still_opens_the_session():
    v = venture("V-LUMA")
    r = actions.start_practice(v, Flaky(broken=True), "m1", "customer", "discovery")
    assert r.persona and r.messages[0].text.startswith("Hi, I'm ")
    q = actions.start_practice(v, Flaky(broken=True), "m1", "judge", "qa")
    assert practice.spec("judge").asks[0] in q.messages[0].text


# ---- what each character knows (access rule 8) ----
def test_the_customer_knows_who_they_are_and_nothing_about_the_idea():
    v, coach = venture(), ScriptedCoach()
    v.conversation.append(Message("m1", "Mentor-only remark.", mentor=v.lead_mode))
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    view = access.character_view(v, r, "Deck text: we charge $3 per item")
    assert practice.segment(v) in view and r.persona in view and "know nothing about the team's idea" in view
    for secret in ("Campus Loop", "$3", "Residence Life", "listing", v.hypotheses[1].statement, "Mentor-only",
                   "Deck text"):
        assert secret not in view
    assert practice.material(v, MemoryFileStore(), r) == ""


def test_the_judge_reads_the_overview_and_the_chosen_material_only():
    v, coach, store = venture(), ScriptedCoach(), MemoryFileStore()
    actions.upload_file(v, coach, store, "m1", "Pitch deck.md", b"# Campus Loop\nWe sold 12 fridges at the pilot.", "")
    v.conversation.append(Message("m1", "Mentor-chat-only remark.", mentor=v.lead_mode))
    deck = v.files[-1]
    assert practice.latest_deck(v) is deck and practice.default_files(v, "judge") == [deck.id]
    assert practice.default_files(v, "customer") == []
    c, _ = actions.request_consultant(v, coach, "m1", "pricing")
    actions.consult_message(v, coach, c.id, "m1", "Consultant-only remark about the hallway.")
    other = actions.start_practice(v, coach, "m2", "challenger", "holes")
    actions.practice_message(v, coach, other.id, "m2", "Practice-only remark: we are worried.")
    r = actions.start_practice(v, coach, "m1", "judge", "pitch", file_ids=(deck.id,), files=store)
    view = access.character_view(v, r, practice.material(v, store, r))
    assert "VENTURE: Campus Loop" in view and "Pitch deck.md" in view and "Text (start):" in view
    for secret in ("Consultant-only", "Practice-only", "Mentor-chat-only", "Move-out interview notes",
                   "KEY-QUESTION ANSWERS"):
        assert secret not in view
    assert "Text (start):" not in practice.material(v, None, r)  # without the store: the summary only


def test_the_challenger_reads_every_record_and_ip_sensitive_ventures_stay_non_technical():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "challenger", "holes")
    view = access.character_view(v, r)
    for record in ("2 of 3 interviewees said they would only use it if it is free", "Offer prepaid $3 listings",
                   "Interview 2 more movers", "Move-out interview notes.md", "Residence Life approved it"):
        assert record in view
    assert "(H2)" not in view and "X-fee" not in view  # no internal ids
    luma, store = venture("V-LUMA"), MemoryFileStore()
    actions.upload_file(luma, coach, store, "m1", "Pitch deck.md", b"Pitch for hospitals.\n\nDetails: optical bench.", "")
    r = actions.start_practice(luma, coach, "m1", "challenger", "premortem", file_ids=(luma.files[-1].id,),
                               files=store)
    material = practice.material(luma, store, r)
    view = access.character_view(luma, r, material)
    assert access.IP_RULE in view and "(withheld: IP-sensitive venture)" in view
    assert "Pitch deck.md" in material and "Text (start):" not in material  # summaries only


# ---- the conversation ----
def test_every_message_gets_a_reply_and_a_failed_reply_keeps_the_message():
    v = venture()
    r = actions.start_practice(v, ScriptedCoach(), "m1", "judge", "qa")
    coach = Flaky(turn_fail=1)
    with pytest.raises(RuntimeError):
        actions.practice_message(v, coach, r.id, "m1", "Students moving out of residence halls; we talked to 3.")
    assert r.messages[-1].author == "m1" and practice.awaiting_reply(r)
    reply = actions.practice_retry(v, coach, r.id, "m1")
    assert reply.author == CHARACTER and not practice.awaiting_reply(r)
    with pytest.raises(ValueError):
        actions.practice_retry(v, coach, r.id, "m1")
    with pytest.raises(PermissionError):
        actions.practice_message(v, coach, r.id, "outsider", "hi")


def test_the_prepared_pitch_is_timed_questioned_and_wrapped_up():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "judge", "pitch")
    lines = prepared("V-CAMPUS", "judge", "pitch")
    assert coach.practice_suggestions(v, r, "m1") == lines
    play(v, coach, r, lines)
    assert r.wrapped_up and coach.practice_suggestions(v, r, "m1") == []
    timing = practice.pitch_timing(r)
    assert timing.target == 180 and not timing.over and timing.label.endswith("(target 3:00)")
    with pytest.raises(ValueError, match="wrapped up"):
        actions.practice_message(v, coach, r.id, "m1", "One more thing!")
    actions.keep_practising(v, r.id, "m1")
    actions.practice_message(v, coach, r.id, "m1", "One more thing: we start in one hall.")
    assert r.messages[-1].author == CHARACTER


def test_scripted_characters_without_prepared_lines():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "challenger", "holes")
    reply = actions.practice_message(v, coach, r.id, "m1", "We already have 40 pre-orders.")
    assert "Your records don't show 40" in reply.text  # it points out what the records don't support
    reply = actions.practice_message(v, coach, r.id, "m1", "Honestly, we don't know yet.")
    assert reply.text.startswith("Fair, that's honest.")
    while not r.wrapped_up:
        actions.practice_message(v, coach, r.id, "m1", "We are not sure.")
    assert practice.turns(r) <= practice.spec("challenger").wrap_after
    luma = venture("V-LUMA")
    c = actions.start_practice(luma, coach, "m1", "customer", "discovery")
    assert "Maybe?" in actions.practice_message(luma, coach, c.id, "m1", "Would you use a sensor like this?").text
    assert "last time" in actions.practice_message(luma, coach, c.id, "m1", "Tell me about the last time.").text
    j = actions.start_practice(v, coach, "m1", "judge", "pitch")
    long_pitch = " ".join(["word"] * 500)
    assert actions.practice_message(v, coach, j.id, "m1", long_pitch).text.startswith("That ran about 3:34, over")


def test_hints_are_whispered_and_counted():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    actions.practice_message(v, coach, r.id, "m1", "Would you pay $3 for this?")
    hint = actions.practice_hint(v, coach, r.id, "m1")
    assert "last time" in hint and r.hints == [hint]
    assert hint not in access.character_view(v, r) and all(hint not in m.text for m in r.messages)
    assert actions.practice_hint(v, Flaky(broken=True), r.id, "m1")  # a failed hint falls back to the rules
    feedback = actions.end_practice(v, coach, r.id, "m1")
    assert feedback.hints_used == 2


# ---- feedback ----
def test_prepared_lines_get_the_prepared_feedback():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "judge", "pitch")
    with pytest.raises(ValueError, match="nothing to give feedback"):
        actions.end_practice(v, coach, r.id, "m1")
    play(v, coach, r, prepared("V-CAMPUS", "judge", "pitch"))
    feedback = actions.end_practice(v, coach, r.id, "m1")
    assert r.status == RehearsalStatus.DONE and r.ended_at and feedback.written_at
    assert feedback.overall == 3.1 and set(feedback.scores) == {d.id for d in practice.spec("judge").rubric}
    assert "waitlist" in feedback.unsupported_claims[0] and len(feedback.fixes) == 3 and not feedback.simplified
    with pytest.raises(ValueError):
        actions.practice_message(v, coach, r.id, "m1", "Hello again")
    with pytest.raises(ValueError):
        actions.end_practice(v, coach, r.id, "m1")


def test_keyword_feedback_rewards_past_behaviour_and_flags_claims_the_records_dont_support():
    v, coach = venture(), ScriptedCoach()
    weak = actions.start_practice(v, coach, "m1", "customer", "discovery")
    play(v, coach, weak, ["Would you use an app that sells your stuff?", "Would you pay $3?",
                          "Don't you think that's useful?"])
    good = actions.start_practice(v, coach, "m1", "customer", "discovery")
    play(v, coach, good, ["Tell me about the last time you moved out.", "How much did the fridge cost you?",
                          "What did you do with it?", "Could I check in with you next week?"])
    weak_fb, good_fb = practice.plain_feedback(v, weak), practice.plain_feedback(v, good)
    assert weak_fb.simplified and weak_fb.scores["past"] < good_fb.scores["past"]
    assert weak_fb.scores["open"] < good_fb.scores["open"] and good_fb.scores["next_step"] > weak_fb.scores["next_step"]
    assert weak_fb.overall < good_fb.overall and weak_fb.fixes and weak_fb.checks == []

    r = actions.start_practice(v, coach, "m1", "challenger", "premortem")
    play(v, coach, r, ["We have 40 pre-orders from movers.", "3 of 3 interviewees left items behind.",
                       "Nobody has paid yet.", "In May we offer prepaid listings to 10 movers.",
                       "Students already paid us deposits."])
    claims = practice.unsupported_claims(v, r)
    assert len(claims) == 2 and "don't show 40" in claims[0] and "no payment" in claims[1]
    plans = [s for s, _ in practice.find_unsupported(v, ["We'd use the prize for 300 crates.",
                                                         "40 students said they would pay."])]
    assert plans == ["40 students said they would pay."]  # the team's own plan is not a claim about what happened
    feedback = practice.plain_feedback(v, r)
    assert feedback.unsupported_claims == claims and feedback.scores["consistency"] <= 3
    assert feedback.problems and feedback.problems[0].startswith("Sellers will pay a $3 fee per item")
    assert all("→" in q for q in feedback.tough_questions)


def test_a_failed_feedback_falls_back_to_the_keyword_checks():
    v = venture()
    r = actions.start_practice(v, ScriptedCoach(), "m1", "judge", "qa")
    actions.practice_message(v, ScriptedCoach(), r.id, "m1", "We interviewed 3 students; nobody has paid yet.")
    feedback = actions.end_practice(v, Flaky(broken=True), r.id, "m1")
    assert feedback.simplified and r.status == RehearsalStatus.DONE


def test_scores_are_kept_to_the_rubric():
    v = venture()
    r = actions.start_practice(v, ScriptedCoach(), "m1", "challenger", "holes")
    actions.practice_message(v, ScriptedCoach(), r.id, "m1", "We don't know yet.")
    practice.finish(v, r, RehearsalFeedback(scores={"honesty": 9, "evidence": "2", "made_up": 4, "clarity": None}),
                    by="m1")
    assert r.feedback.scores == {"honesty": 5, "evidence": 2} and r.feedback.overall == 3.5


def test_pitch_timing_from_the_words():
    assert practice.estimate(" ".join(["w"] * 420), 180).label == "420 words ≈ 3:00 (target 3:00)"
    assert practice.estimate(" ".join(["w"] * 500), 180).over and not practice.estimate("one two", 180).over
    assert practice.estimate("one two three").label == "3 words ≈ 0:01"


# ---- privacy (access rule 8) and the records ----
def test_practice_never_changes_records_and_stays_out_of_the_mentors_and_consultants_view():
    v, coach = venture(), ScriptedCoach()
    before = (to_dict(v.hypotheses), to_dict(v.next_steps), to_dict(v.canvas), to_dict(v.answers), len(v.changes),
              len(v.conversation), len(v.timeline))
    r = actions.start_practice(v, coach, "m1", "judge", "pitch")
    play(v, coach, r, prepared("V-CAMPUS", "judge", "pitch"))
    actions.end_practice(v, coach, r.id, "m1")
    after = (to_dict(v.hypotheses), to_dict(v.next_steps), to_dict(v.canvas), to_dict(v.answers), len(v.changes),
             len(v.conversation), len(v.timeline))
    assert before == after
    window, _ = memory.window(v)
    seen = memory.lead_context(v) + str(window)
    c = actions.invite_consultant(v, "pricing", "Is $3 right?", "Brief", "eir")
    seen += access.consultant_view(v, c)
    assert "waitlist" not in seen and r.feedback.verdict not in seen
    with pytest.raises(PermissionError):
        access.lead_view_of_practice(v, r)


def test_only_sent_feedback_reaches_the_mentor_never_the_conversation():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "challenger", "holes")
    play(v, coach, r, prepared("V-CAMPUS", "challenger", "holes"))
    with pytest.raises(ValueError, match="End the session first"):
        practice.share(r, by="m1")
    actions.end_practice(v, coach, r.id, "m1")
    practice.share(r, by="m2")
    with pytest.raises(ValueError, match="already sent"):
        practice.share(r, by="m2")
    text = access.lead_view_of_practice(v, r)
    assert text.startswith("Practice feedback sent by Bob: Challenger · Find the holes · Realistic")
    assert "Overall 4.2 of 5" in text and r.feedback.problems[0] in text and "nothing in it is evidence" in text
    assert all(m.text not in text for m in r.messages)  # never the conversation
    with pytest.raises(ValueError, match="sent to your Virtual EIR"):
        actions.delete_practice(v, r.id, "m1")


def test_staff_see_nothing_of_practice():
    repo = InMemoryRepository(demo_ventures())
    v, coach = repo.get("V-CAMPUS"), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    staff = Account("roberto", "AIN staff", Role.STAFF)
    entry = next(e for e in access.staff_directory(staff, repo) if e.venture_id == v.id)
    assert r.persona not in str(entry) and not access.shared_briefs_for_staff(staff, v)
    assert not access.can_open(staff, v)


# ---- the Practice page's data ----
def test_recommended_practice_follows_the_venture():
    campus = venture()
    rec = practice.recommended(campus)
    assert (rec.character, rec.scenario, rec.difficulty) == ("judge", "pitch", Difficulty.REALISTIC)
    assert "pitch deck" in rec.reason
    luma = venture("V-LUMA")
    assert (practice.recommended(luma).character, practice.recommended(luma).scenario) == ("customer", "discovery")
    luma.done.append("customer_discovery")
    assert practice.recommended(luma).scenario == "solution"
    campus.lead_mode = LeadMode.OPTIMIZE
    assert practice.recommended(campus).character == "challenger"


def test_history_practise_again_and_delete():
    v, coach = venture(), ScriptedCoach()
    first = actions.start_practice(v, coach, "m1", "challenger", "assumption", Difficulty.TOUGH, assumption_id="H2")
    customer = actions.start_practice(v, coach, "m2", "customer", "discovery")
    assert practice.history(v) == [customer, first] and practice.history(v, "challenger") == [first]
    assert practice.in_progress(v) == [customer, first]
    again = actions.practice_again(v, coach, first.id, "m3")
    assert again.id != first.id and (again.character, again.scenario, again.difficulty, again.assumption_id) == \
        ("challenger", "assumption", Difficulty.TOUGH, "H2")
    assert again.started_by == "m3" and practice.history(v)[0] is again
    actions.delete_practice(v, customer.id, "m2")
    assert v.rehearsal(customer.id) is None


def test_a_session_with_feedback_is_saved_and_loaded():
    v, coach = venture(), ScriptedCoach()
    r = actions.start_practice(v, coach, "m1", "customer", "discovery", Difficulty.FRIENDLY)
    actions.practice_hint(v, coach, r.id, "m1")
    play(v, coach, r, prepared("V-CAMPUS", "customer", "discovery"))
    actions.end_practice(v, coach, r.id, "m1")
    loaded = from_dict(type(v), to_dict(v)).rehearsal(r.id)
    assert loaded == r and loaded.feedback.checks and loaded.feedback.hints_used == 1
    assert loaded.difficulty == Difficulty.FRIENDLY and loaded.persona.startswith("Maya")
