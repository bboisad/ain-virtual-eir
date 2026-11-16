"""Member journeys through the app with the scripted mentor and consultants; no API credentials are used.

Workspace = top bar (Virtual EIR · Overview · Action Plan · Practice, ⋯ menu with dialogs); the Virtual EIR page has
the consultant rail and drawer; the Overview is the project's homepage (intro, status, core content, project files).
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from eir import practice, roadmap
from eir.coach.scripted import ScriptedCoach
from eir.models import (CHARACTER, CONSULTANT, EIR, ConsultationStatus, ExperimentStatus, Goal, HypothesisStatus,
                        LeadMode, Module, ReviewState, Rung, StepStatus, Traction, Verdict)
from eir.seed import consult_script_for
from ui.state import core as state_core

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class DemoCoach(ScriptedCoach):
    """The scripted mentor, counting turns; `fail` makes the next n turns raise like a dropped connection."""

    def __init__(self):
        super().__init__()
        self.turns, self.fail = 0, 0

    def lead_turn(self, *args, **kwargs):
        self.turns += 1
        if self.fail:
            self.fail -= 1
            raise RuntimeError("the endpoint timed out")
        return super().lead_turn(*args, **kwargs)


@pytest.fixture(autouse=True)
def demo_coach(monkeypatch):
    coach = DemoCoach()
    monkeypatch.setattr(state_core, "coach", lambda: coach)
    return coach


def ok(at):
    assert not at.exception, at.exception


def click(at, label=None, key=None):
    button = at.button(key=key) if key else next(b for b in at.button if b.label == label)
    button.click().run()
    ok(at)


def sign_in(account_id, at=None):
    at = at or AppTest.from_file(APP, default_timeout=30).run()
    ok(at)
    at.selectbox[0].set_value(account_id).run()
    click(at, "Sign in")
    return at


def open_campus(account_id="alice"):
    at = sign_in(account_id)
    click(at, key="open_V-CAMPUS")
    assert at.session_state["app_state"].page == "Mentor"
    return at


def venture(at, vid="V-CAMPUS"):
    return at.session_state["repo"].get(vid)


def nav(at, vid="V-CAMPUS"):
    """The top navigation. Its key changes when code changes the page (ui/state/core.py nav_key)."""
    return at.segmented_control(key=f"topnav_{vid}_{at.session_state['app_state'].nav_round}")


def go(at, page, vid="V-CAMPUS"):
    nav(at, vid).set_value(page).run()
    ok(at)
    assert at.session_state["app_state"].page == page and nav(at, vid).value == page


def visible_text(at):
    return " ".join(item.value for group in (at.markdown, at.caption, at.info, at.success, at.warning, at.error)
                    for item in group)


def send(at, text):
    at.chat_input[0].set_value(text).run()
    ok(at)


def menu(at, item):
    click(at, key=f"menu_{item}")


# ---- Mentor ----
def test_a_team_lands_on_its_mentor_with_a_briefing():
    at = open_campus("bob")
    text = visible_text(at)
    assert "Current focus:" in text and "Will sellers really pay" in text and "Last time (Oct 5)" in text
    assert "LumaSense" not in text and at.chat_input[0].placeholder == "Message your Launch Virtual EIR"
    assert list(nav(at).options) == ["Virtual EIR", "Overview", "Action Plan", "Practice"]


def test_every_message_gets_a_reply_and_its_record_updates_can_be_undone(demo_coach):
    at = open_campus("bob")
    v = venture(at)
    prepared = next(b for b in at.button if b.key.startswith("suggest_") and "2 more interviews" in b.label)
    prepared.click().run()
    ok(at)
    reply = v.conversation[-1]
    assert reply.author == EIR and len(reply.change_groups) == 3 and demo_coach.turns == 1
    assert v.step("S1").status == StepStatus.DONE and v.hypothesis("H4") is not None
    assert any(e.label == "Record updates (3)" for e in at.expander)

    click(at, key=f"undo_{reply.change_groups[2]}")  # the new assumption H4
    assert v.hypothesis("H4") is None and "Undone by Bob" in visible_text(at)
    assert v.step("S1").status == StepStatus.DONE  # the other updates stay

    send(at, "We think it's fine.")
    assert [m.author for m in v.conversation[-2:]] == ["m2", EIR] and demo_coach.turns == 2


def test_a_failed_reply_keeps_the_message_and_can_be_asked_again(demo_coach):
    at = open_campus()
    v = venture(at)
    demo_coach.fail = 1
    send(at, "What should we test first?")
    assert [m.author for m in v.conversation] == ["m1"]
    assert any("Your message was kept" in e.value and "timed out" in e.value for e in at.error)
    click(at, key="retry_V-CAMPUS")
    assert [m.author for m in v.conversation] == ["m1", EIR] and not any(b.key == "retry_V-CAMPUS" for b in at.button)


def test_the_optimize_mentor_checks_evidence_first_and_the_team_decides_to_switch():
    at = sign_in("priya")
    create_project(at, "Lab Share", traction=Traction.YES, goal=Goal.IMPROVE)
    assert "We recommend **Optimize**" in visible_text(at)
    click(at, "Start with Optimize")
    v = venture(at, at.session_state["app_state"].venture_id)
    assert v.lead_mode == LeadMode.OPTIMIZE and v.mode_choice.recommended == LeadMode.OPTIMIZE
    send(at, "Help us grow faster")
    reply = v.conversation[-1]
    assert reply.suggested_mode == LeadMode.LAUNCH and "Launch Virtual EIR" in reply.text
    click(at, key=f"switch_{reply.id}")
    assert v.lead_mode == LeadMode.LAUNCH and v.mode_history[-1].reason == "Suggested by the Virtual EIR"
    assert any(e.label.startswith("Earlier conversation with the Optimize Virtual EIR") for e in at.expander)
    assert at.chat_input[0].placeholder == "Message your Launch Virtual EIR"


# ---- consultants: the rail and the drawer ----
def drawer(at):
    return at.session_state["app_state"].drawer


def test_a_consultant_from_the_rail_opens_in_a_drawer_that_collapses_without_ending():
    at = open_campus()
    v = venture(at)
    assert {b.key for b in at.button if b.key and b.key.startswith("rail_")} == {"rail_pricing", "rail_strategy",
                                                                                "rail_funding"}
    click(at, key="rail_pricing")  # not used yet: the Virtual EIR brings them in with a brief
    c = v.open_consultation("pricing")
    assert c is not None and drawer(at) == "pricing" and v.conversation[-1].consultation_id == c.id
    assert any("an AI, not a real person" in m.value for m in at.markdown)
    assert [i.key for i in at.chat_input] == [f"consult_input_{c.id}"]  # the Virtual EIR's input is hidden meanwhile
    at.chat_input(key=f"consult_input_{c.id}").set_value("We never asked anyone about the price.").run()
    ok(at)
    assert [m.author for m in c.messages] == [CONSULTANT, "m1", CONSULTANT]

    click(at, key="drawer_collapse")
    assert drawer(at) == "" and c.status == ConsultationStatus.OPEN
    assert [i.key for i in at.chat_input] == ["mentor_input_V-CAMPUS"]
    click(at, key=f"open_consult_{v.conversation[-1].id}")  # from the Virtual EIR's reply
    assert drawer(at) == "pricing" and "We never asked anyone about the price." in visible_text(at)


def test_a_consultation_ends_with_a_summary_the_student_previews_and_the_mentor_acts_on():
    at = open_campus()
    v = venture(at)
    click(at, key="rail_pricing")
    c = v.open_consultation("pricing")
    for _ in consult_script_for("V-CAMPUS", "pricing").lines:  # the prepared demo messages, in order
        next(b for b in at.button if b.key and b.key.startswith(f"csuggest_{c.id}_")).click().run()
        ok(at)
    assert c.proposed_end and "thinks your Virtual EIR's question is answered" in visible_text(at)
    click(at, key=f"review_{c.id}")
    assert c.draft is not None and c.status == ConsultationStatus.OPEN
    assert "Summary for your Virtual EIR" in visible_text(at) and "Needs a human EIR:** no" in visible_text(at)
    at.text_input(key=f"consult_note_{c.id}").input("I still want to try $3 first")
    click(at, key=f"send_{c.id}")
    assert c.status == ConsultationStatus.DONE and c.summary.student_note == "I still want to try $3 first"
    assert drawer(at) == "" and v.conversation[-1].consultation_id == c.id
    assert any(e.label == "Record updates (2)" for e in at.expander)  # the suggested to-dos, each undoable
    click(at, key="rail_pricing")  # done: the drawer shows what was sent
    assert any(b.key == "again_pricing" for b in at.button) and "Your note to your Virtual EIR" in visible_text(at)


# ---- project files ----
SURVEY = b"# Pricing survey\n- 28 of 40 said they would pay $3 to sell a mini-fridge.\n"


def share(at, name="Pricing survey.md", data=SURVEY, note=""):
    """What the Virtual EIR chat does with an attachment (the test client cannot attach files to a chat message)."""
    from eir import actions
    actions.upload_file(venture(at), ScriptedCoach(), at.session_state["filestore"], "m1", name, data, note)
    at.run()
    ok(at)


def dialog(at):
    return at.session_state["app_state"].dialog


def page(at):
    return at.session_state["app_state"].page


def test_a_shared_file_is_listed_on_the_overview_and_managed_in_its_dialog():
    at = open_campus()
    share(at, note="Our survey results")
    v = venture(at)
    f = v.files[-1]
    assert any(c.value.endswith("Pricing survey.md · version 1") for c in at.caption)
    go(at, "Overview")
    assert any(b.key == f"ov_file_{f.id}" for b in at.button) and "discussed" in visible_text(at)  # the latest files
    click(at, key="ov_all_files_V-CAMPUS")
    assert dialog(at) == "ov_files" and "Discussed with your Virtual EIR" in visible_text(at)
    assert any(b.key == f"file_chat_{f.id}" for b in at.button)
    assert "Open revisions: Revise Pricing survey.md" in visible_text(at)  # checked against the next version
    assert at.button(key=f"file_rm_{f.id}").disabled  # removing needs a confirmation
    at.checkbox(key=f"file_rm_ok_{f.id}").check().run()
    click(at, key=f"file_rm_{f.id}")
    assert v.file(f.id) is None and dialog(at) == "" and not any(b.key == f"ov_file_{f.id}" for b in at.button)


def test_a_file_added_on_the_overview_waits_until_the_team_asks_to_discuss_it(demo_coach):
    at = open_campus()
    go(at, "Overview")
    v = venture(at)
    click(at, key="ov_add_V-CAMPUS")
    at.file_uploader(key="ov_upload_V-CAMPUS_0").upload("Pricing survey.md", SURVEY, "text/markdown").run()
    ok(at)
    f = next(x for x in v.files if x.name == "Pricing survey.md")
    assert demo_coach.turns == 0 and not any(m.file_id == f.id for m in v.conversation)  # saved only
    assert dialog(at) == "ov_add_file" and "Saved Pricing survey.md" in visible_text(at)
    assert at.file_uploader(key="ov_upload_V-CAMPUS_1").value is None  # the upload box is empty again
    click(at, key=f"ov_notnow_{f.id}")
    assert dialog(at) == "" and "Saved Pricing survey.md" not in visible_text(at)
    click(at, key=f"ov_file_{f.id}")  # its own dialog: not read yet, with a preview
    assert "Not discussed yet" in visible_text(at) and "28 of 40 said" in " ".join(t.value for t in at.text)
    assert f.latest.summary.startswith("Document excerpt (not reviewed)")

    click(at, key="ov_add_V-CAMPUS")
    at.file_uploader(key="ov_upload_V-CAMPUS_1").upload("Pricing survey v2.md", SURVEY + b"- 3 prepaid.\n",
                                                         "text/markdown").run()
    ok(at)
    assert f.latest.number == 2 and "Saved Pricing survey v2.md" in visible_text(at)
    at.text_input(key=f"ov_note_{f.id}").input("Is the $3 price convincing?")
    click(at, key=f"ov_discuss_new_{f.id}")
    assert page(at) == "Mentor" and nav(at).value == "Mentor" and dialog(at) == "" and demo_coach.turns == 1
    asked = v.conversation[-2]
    assert (asked.author, asked.text, asked.file_id, asked.file_version) == ("m1", "Is the $3 price convincing?", f.id,
                                                                            2)
    assert v.conversation[-1].author == EIR and not f.latest.summary.startswith("Document excerpt")
    go(at, "Overview")
    click(at, key=f"ov_file_{f.id}")
    assert "Discussed with your Virtual EIR" in visible_text(at)
    click(at, key=f"file_chat_{f.id}")
    assert page(at) == "Mentor" and nav(at).value == "Mentor"


def test_a_failed_discussion_keeps_the_file_in_the_chat_to_ask_again(demo_coach):
    at = open_campus()
    go(at, "Overview")
    v = venture(at)
    notes = next(x for x in v.files if x.name == "Move-out interview notes.md")
    assert "read by your Virtual EIR" in visible_text(at)  # the seeded notes were summarized in an earlier session
    click(at, key=f"ov_file_{notes.id}")
    demo_coach.fail = 1
    click(at, key=f"file_discuss_{notes.id}")
    assert page(at) == "Mentor" and nav(at).value == "Mentor"  # the top navigation follows
    assert v.conversation[-1].file_id == notes.id and v.conversation[-1].author == "m1"
    assert any("Your message was kept" in e.value and "timed out" in e.value for e in at.error)
    click(at, key="retry_V-CAMPUS")
    assert v.conversation[-1].author == EIR and demo_coach.turns == 2


def test_the_same_file_twice_is_refused_in_the_upload_dialog():
    at = open_campus()
    go(at, "Overview")
    click(at, key="ov_add_V-CAMPUS")
    at.file_uploader(key="ov_upload_V-CAMPUS_0").upload("Pricing survey.md", SURVEY, "text/markdown").run()
    at.file_uploader(key="ov_upload_V-CAMPUS_1").upload("Pricing survey (1).md", SURVEY, "text/markdown").run()
    ok(at)
    assert any("was not saved: This is the same as version 1" in e.value for e in at.error)
    assert len(venture(at).files) == 2 and at.file_uploader(key="ov_upload_V-CAMPUS_2").value is None


def test_a_link_is_listed_with_what_the_team_says_it_shows():
    at = open_campus()
    go(at, "Overview")
    click(at, key="ov_add_V-CAMPUS")
    at.text_input(key="link_url_V-CAMPUS").input("https://campusloop.example").run()
    at.text_input(key="link_what_V-CAMPUS").input("Our landing page with the waitlist form").run()
    click(at, key="link_add_V-CAMPUS")
    link = venture(at).files[-1]
    assert link.url == "https://campusloop.example" and dialog(at) == ""
    click(at, key=f"ov_file_{link.id}")
    assert "waitlist form" in visible_text(at)
    assert not any(b.key == f"file_discuss_{link.id}" for b in at.button)  # links are never opened or read


# ---- Overview ----
def test_the_overview_says_what_we_do_where_we_are_stuck_and_what_next():
    at = open_campus()
    go(at, "Overview")
    text = visible_text(at)
    assert "## Campus Loop" in text and "Team statement" in text and "Virtual EIR suggestion" in text
    assert "### Will sellers really pay \\$3 per item?" in text and "fatal if wrong" in text  # the focus card
    for line in ("Why now", "Evidence for", "Evidence against", "Still missing", "Next step"):
        assert line in text, line
    assert "Offer prepaid \\$3 listings to 10 movers at the Residence Life table" in text
    assert at.button(key="ov_cta_V-CAMPUS").label == "Review and start the test"  # a draft experiment
    assert "✓ Customer discovery" in text and "Now: Who decides on the purchase" in text  # progress, in words
    assert "M2 · Pitch deck · step" not in text  # the step number is only in the key questions
    assert at.button(key="ov_core_V-CAMPUS_customer").label == "Target customer"  # the snapshot
    assert "#### Recent activity" in text and "#### Files" in text and "Move-out interview notes.md" in [
        b.label for b in at.button]
    assert not any(e.label.startswith(("Riskiest", "All assumptions", "Evidence map")) for e in at.expander)
    assert "Customer statements · Level 3" in text  # in the evidence popover, with where it comes from
    click(at, key="ov_cta_V-CAMPUS")
    assert page(at) == "Action Plan" and nav(at).value == "Action Plan"


def test_the_key_questions_and_the_step_check_open_from_the_progress():
    at = open_campus()
    go(at, "Overview")
    click(at, key="ov_questions_V-CAMPUS")
    assert dialog(at) == "ov_questions" and "M2 · Pitch deck · step" in visible_text(at)
    click(at, key="check_pitch_deck")
    assert venture(at).judgments[-1].verdict == Verdict.NOT_YET and "Not yet" in visible_text(at)


def box(widgets, prefix):
    """A box that edits saved text: its key ends with a tag of that text (ui/pages/overview.py _key)."""
    return next(w for w in widgets if w.key and w.key.startswith(prefix + "_"))


def test_the_team_edits_its_snapshot_and_intro_in_dialogs_and_the_levels_stay():
    at = open_campus("bob")
    go(at, "Overview")
    v = venture(at)
    graded = (v.canvas["Revenue Streams"].text, v.canvas["Revenue Streams"].rung)
    click(at, key="ov_core_V-CAMPUS_revenue")
    assert dialog(at) == "ov_core:revenue" and "What your records show" in visible_text(at)
    box(at.text_area, "core_text_V-CAMPUS_revenue").input("A $1 pickup fee paid by buyers")
    click(at, key="core_save_V-CAMPUS_revenue")
    assert v.profile.revenue == "A $1 pickup fee paid by buyers" and dialog(at) == ""
    assert "A \\$1 pickup fee paid by buyers" in visible_text(at)
    assert (v.canvas["Revenue Streams"].text, v.canvas["Revenue Streams"].rung) == graded  # the level stays
    click(at, key="ov_edit_intro_V-CAMPUS")
    box(at.text_input, "intro_line_V-CAMPUS").input("Move-out resale for students with bulky items")
    click(at, key="intro_save_V-CAMPUS")
    assert v.description == "Move-out resale for students with bulky items" and v.profile.completed_by == "m2"
    assert "Bob · " in visible_text(at)
    click(at, key="ov_edit_intro_V-CAMPUS")
    box(at.text_input, "intro_name_V-CAMPUS").input(" ")
    click(at, key="intro_save_V-CAMPUS")
    assert "Enter a project name." in visible_text(at) and v.name == "Campus Loop" and dialog(at) == "ov_intro"


def test_the_virtual_eirs_canvas_text_is_a_draft_the_team_can_adopt():
    at = open_campus()
    v = venture(at)
    v.profile.solution = ""  # the team has not written it; the canvas holds what the Virtual EIR recorded
    go(at, "Overview")
    assert "Drafted by your Virtual EIR" in visible_text(at)
    click(at, key="ov_core_V-CAMPUS_solution")
    click(at, key="ov_adopt_V-CAMPUS_solution")
    assert v.profile.solution == v.canvas["Value Propositions"].text and dialog(at) == ""
    assert "Drafted by your Virtual EIR" not in visible_text(at)


def test_the_intro_dialog_shows_a_name_changed_in_the_settings():
    at = open_campus()
    go(at, "Overview")
    menu(at, "settings")
    next(t for t in at.text_input if t.label == "Project name" and not t.key).input("Campus Loop Co")
    click(at, "Save settings")
    click(at, key="ov_edit_intro_V-CAMPUS")
    assert box(at.text_input, "intro_name_V-CAMPUS").value == "Campus Loop Co"
    click(at, key="intro_save_V-CAMPUS")
    assert venture(at).name == "Campus Loop Co"


def test_a_new_project_starts_with_a_conversation_and_fills_in_as_the_team_talks(demo_coach):
    at = sign_in("priya")
    create_project(at, "Lab Share")
    click(at, "Start with Launch")
    vid = at.session_state["app_state"].venture_id
    go(at, "Overview", vid)
    assert "Your project, just started." in visible_text(at) and not any(b.key == f"ov_cta_{vid}" for b in at.button)
    click(at, key=f"ov_start_upload_{vid}")
    assert dialog(at) == "ov_add_file"
    click(at, key=f"ov_start_invite_{vid}")
    assert dialog(at) == "members"
    click(at, key=f"ov_start_chat_{vid}")
    assert page(at) == "Mentor" and nav(at, vid).value == "Mentor"
    send(at, "We want to help grad students share idle lab equipment.")
    go(at, "Overview", vid)
    assert "Your project, just started." not in visible_text(at) and any(b.key == f"ov_cta_{vid}" for b in at.button)


def test_the_action_plan_starts_with_the_assumptions_riskiest_first():
    at = open_campus()
    go(at, "Action Plan")
    text = visible_text(at)
    assert text.index("#### Assumptions") < text.index("#### Experiments") < text.index("#### Tasks")
    assert text.index("H2 · Sellers will pay") < text.index("H1 · ")  # fatal if wrong, so it comes first
    at.text_input(key="new_assumption_V-CAMPUS").input("Buyers pick items up within a day").run()  # enables Add
    click(at, key="add_assumption_V-CAMPUS")
    assert venture(at).hypotheses[-1].statement == "Buyers pick items up within a day"


def test_the_menu_has_the_project_plan_and_stepping_back():
    at = open_campus()
    v = venture(at)
    menu(at, "plan")
    assert dialog(at) == "plan" and "A one-page preliminary project plan" in visible_text(at)
    menu(at, "back")
    at.text_input(key="rm_back_reason_V-CAMPUS").input("Fee test: 0 of 10 movers paid $3")
    click(at, key="rm_back_V-CAMPUS")
    assert v.module == Module.M1 and dialog(at) == ""


EVIDENCE = {1: "LLC, advised by the campus law clinic",
            2: "According to an industry report, 3 apps do this; none serve campus move-out",
            3: "We interviewed 12 movers; 9 said the RA decides",
            4: "15 students signed up for the pilot and 6 pre-ordered at $3"}


def test_the_virtual_eir_checks_a_step_and_an_eir_confirms_it(demo_coach):
    at = open_campus("alice")
    go(at, "Overview")
    click(at, key="ov_questions_V-CAMPUS")
    for q in roadmap.deliverable("pitch_deck").questions:
        box(at.text_area, f"ans_V-CAMPUS_{q.id}").set_value(EVIDENCE[int(q.need)]).run()
        click(at, key=f"save_V-CAMPUS_{q.id}")
    v = venture(at)
    assert v.module == Module.M2 and v.answer("pd_commitment").rung == Rung.PAID  # graded, not chosen
    click(at, key="check_pitch_deck")
    j = v.judgments[-1]
    assert j.verdict == Verdict.READY and j.review == ReviewState.PENDING and v.module == Module.M3
    assert "An AIN EIR will check this judgment" in visible_text(at)
    assert demo_coach.turns == 0  # the step check never needs the Virtual EIR

    menu(at, "signout")
    at = sign_in("roberto", at)
    assert "1 judgment to check" in visible_text(at)
    i = len(v.judgments) - 1
    at.text_area(key=f"jn_V-CAMPUS_{i}").set_value("Agreed, solid pre-orders").run()
    click(at, key=f"jok_V-CAMPUS_{i}")
    assert venture(at).judgments[i].review == ReviewState.CONFIRMED


# ---- Action Plan ----
def test_an_experiment_is_judged_against_criteria_agreed_in_advance(demo_coach):
    at = open_campus()
    go(at, "Action Plan")
    v = venture(at)
    click(at, key="start_X-fee")
    assert v.experiment("X-fee").status == ExperimentStatus.RUNNING
    assert not any(b.label == "Save draft" for b in at.button)  # the criteria are locked
    at.text_area(key="result_X-fee").set_value("2 of 10 movers prepaid $3").run()
    click(at, key="save_result_X-fee")
    click(at, key="judge_X-fee")
    x, h = v.experiment("X-fee"), v.hypothesis("H2")
    assert x.status == ExperimentStatus.CONCLUDED and h.status == HypothesisStatus.REFUTED and h.rung == Rung.PAID
    assert any("Refuted" in s.value for s in at.success) and demo_coach.turns == 1
    assert v.conversation[-1].author == EIR and v.conversation[-2].text.startswith("Alice asked the Virtual EIR to judge")


def test_a_draft_cannot_start_until_both_criteria_are_written():
    at = open_campus()
    go(at, "Action Plan")
    v = venture(at)
    at.selectbox(key="newx_target_V-CAMPUS").set_value(("assumption", "H1"))
    at.text_area(key="newx_method_V-CAMPUS").input("Ask 5 movers whether they would list items before leaving")
    at.text_input(key="newx_supported_V-CAMPUS").input("4 or more of 5 say yes")
    click(at, "Add the experiment as a draft")
    x = v.experiments[-1]
    assert x.assumption_id == "H1" and x.status == ExperimentStatus.DRAFT and x.method_rung == Rung.SAID
    assert at.button(key=f"start_{x.id}").disabled
    assert "what result refutes it" in visible_text(at)
    assert at.text_area(key="newx_method_V-CAMPUS").value == ""  # the form is empty again


def test_tasks_are_added_and_done_on_the_action_plan():
    at = open_campus()
    go(at, "Action Plan")
    v = venture(at)
    at.text_input(key="task_text_V-CAMPUS").input("Call Residence Life about a table")
    at.selectbox(key="task_owner_V-CAMPUS").set_value("m3")
    click(at, "Add task")
    s = v.next_steps[-1]
    assert (s.text, s.owner, s.created_by) == ("Call Residence Life about a table", "m3", "m1")
    at.text_input(key=f"done_result_{s.id}").input("They offered a table on May 2")
    click(at, key=f"done_{s.id}")
    assert s.status == StepStatus.DONE and s.result == "They offered a table on May 2"


# ---- Practice ----
def session(at):
    """The practice session open on the Practice page, if any."""
    s = at.session_state["app_state"]
    return venture(at).rehearsal(s.rehearsal) if s.rehearsal else None


def test_practice_is_the_fourth_page_with_a_recommendation_and_three_characters():
    at = open_campus()
    go(at, "Practice")
    text = visible_text(at)
    assert "Recommended now" in text and "You're on the pitch deck step" in text and "None yet." in text
    for s in practice.characters():
        assert at.button(key=f"practise_{s.id}").label == "Practise" and s.knows in text


def test_a_recommended_pitch_runs_to_feedback_and_reaches_the_mentor():
    at = open_campus()
    go(at, "Practice")
    click(at, key="practice_rec_start")
    r = session(at)
    assert (r.character, r.scenario) == ("judge", "pitch") and at.button(key=f"pend_{r.id}").disabled
    assert at.chat_input(key=f"practice_input_{r.id}").placeholder == "Type or paste your pitch…"
    while not r.wrapped_up:  # the prepared demo lines, in order
        next(b for b in at.button if b.key and b.key.startswith(f"psuggest_{r.id}_")).click().run()
        ok(at)
    text = visible_text(at)
    assert "Your pitch: 311 words ≈ 2:13 (target 3:00)" in text and "has wrapped up" in text
    assert not at.chat_input  # after the wrap-up: get the feedback, or keep going
    click(at, key=f"pfeedback_{r.id}")
    assert r.feedback is not None and "Fix these first" in visible_text(at) and "3.1" in visible_text(at)
    assert any("waitlist" in w.value for w in at.warning)  # a claim the records don't support
    at.text_input(key=f"pnote_{r.id}").input("The money question froze me")
    click(at, key=f"psend_{r.id}")
    v = venture(at)
    assert r.shared_note == "The money question froze me" and v.conversation[-1].rehearsal_id == r.id
    assert any("Sent. Your Virtual EIR replied" in s.value for s in at.success)
    click(at, key=f"preply_{r.id}")
    assert at.session_state["app_state"].page == "Mentor"
    click(at, key=f"open_practice_{v.conversation[-1].id}")
    assert at.session_state["app_state"].page == "Practice" and session(at) is r


def test_a_customer_interview_from_its_card_with_a_private_hint_continued_later_then_discarded():
    at = open_campus()
    go(at, "Practice")
    click(at, key="practise_customer")
    assert at.session_state["app_state"].practice_setup == "customer/discovery"
    assert at.radio(key="ps_scenario_V-CAMPUS_customer").value == "discovery"
    assert "only who they are" in visible_text(at)
    click(at, key="ps_start_V-CAMPUS")
    r = session(at)
    assert r.persona.startswith("Maya") and at.session_state["app_state"].practice_setup == ""
    box = at.chat_input(key=f"practice_input_{r.id}")
    assert box.placeholder == "Ask Maya a question…"
    box.set_value("Would you pay $3 for this?").run()
    ok(at)
    assert [m.author for m in r.messages] == [CHARACTER, "m1", CHARACTER]
    click(at, key=f"phint_{r.id}")
    assert len(r.hints) == 1 and any("hint-note" in m.value and "last time" in m.value for m in at.markdown)
    click(at, key=f"pback_{r.id}")
    assert session(at) is None and "In progress" in visible_text(at)
    click(at, key=f"psession_open_{r.id}")
    assert session(at) is r
    click(at, key=f"pdiscard_{r.id}")
    assert venture(at).rehearsal(r.id) is None and session(at) is None


def test_the_mentors_practice_suggestion_opens_the_setup_with_its_settings():
    at = open_campus()
    v = venture(at)
    send(at, "We're pitching at Foundry Friday next week. How should we prepare?")
    reply = v.conversation[-1]
    assert reply.practice_suggestion == "judge/pitch"
    click(at, key=f"practice_suggest_{reply.id}")
    s = at.session_state["app_state"]
    assert s.page == "Practice" and s.practice_setup == "judge/pitch"
    assert at.segmented_control(key="ps_character_V-CAMPUS").value == "judge"
    assert at.radio(key="ps_scenario_V-CAMPUS_judge").value == "pitch"


# ---- projects, the menu and its dialogs ----
def create_project(at, name, traction=Traction.NOT_YET, goal=Goal.SHAPE):
    prefix = f"create_project_{at.session_state['app_state'].account_id}"
    at.text_input(key=f"{prefix}_name").input(name)
    at.text_input(key=f"{prefix}_description").input("Share idle lab equipment")
    at.radio(key=f"{prefix}_traction").set_value(traction)
    at.radio(key=f"{prefix}_goal").set_value(goal)
    click(at, "Next: choose your Virtual EIR")


def test_create_a_project_with_the_recommended_mentor_and_invite_a_teammate(demo_coach):
    at = sign_in("priya")
    create_project(at, "Lab Share")
    assert "We recommend **Launch**" in visible_text(at)
    click(at, "Start with Launch")
    s = at.session_state["app_state"]
    v = venture(at, s.venture_id)
    assert s.page == "Mentor" and v.name == "Lab Share" and v.lead_mode == LeadMode.LAUNCH
    assert len(v.members) == 1 and v.members[0].account == "priya"
    send(at, "Let's start by listing the labs we know.")
    assert [m.author for m in v.conversation] == [v.members[0].id, EIR]  # every message gets a reply

    menu(at, "members")
    code = at.code[0].value
    menu(at, "signout")
    sign_in("bob", at)
    assert "Lab Share" not in visible_text(at)
    at.text_input(key="join_code_bob").input(code).run()
    ok(at)
    assert "Lab Share" in visible_text(at) and v.member_for_account("bob") is None  # preview is not acceptance
    click(at, "Join project")
    assert s.page == "Mentor" and s.venture_id == v.id and v.member_for_account("bob") is not None
    assert "Let's start by listing the labs we know." in visible_text(at)


def test_a_human_eir_brief_is_shared_only_with_consent():
    at = open_campus()
    menu(at, "human")
    v = venture(at)
    assert at.button(key="share_V-CAMPUS").disabled
    assert "Roadmap checklist" in next(t for t in at.text_area if t.key.startswith("mentor_draft_")).value
    at.checkbox(key="brief_consent_V-CAMPUS").check().run()
    click(at, key="share_V-CAMPUS")
    assert len(v.shared_briefs) == 1 and any("Shared." in s.value for s in at.success)
    menu(at, "signout")
    at = sign_in("roberto", at)
    assert "Campus Loop" in visible_text(at) and not any(b.key and b.key.startswith("open_") for b in at.button)
    assert any(e.label.endswith(v.shared_briefs[0].topic) for e in at.expander)


def test_switching_the_mentor_from_the_menu_keeps_every_record():
    at = open_campus()
    v = venture(at)
    before = (list(v.hypotheses), list(v.experiments), dict(v.canvas))
    go(at, "Overview")
    menu(at, "switch")
    click(at, key="switch_to_V-CAMPUS")
    assert v.lead_mode == LeadMode.OPTIMIZE and at.session_state["app_state"].page == "Mentor"
    assert nav(at).value == "Mentor"  # the top navigation follows a page change made by code
    assert (list(v.hypotheses), list(v.experiments), dict(v.canvas)) == before
    assert "Switched from the Launch Virtual EIR to the Optimize Virtual EIR" in visible_text(at)
    assert at.chat_input[0].placeholder == "Message your Optimize Virtual EIR"


def test_project_settings_rename_the_project():
    at = open_campus()
    menu(at, "settings")
    next(t for t in at.text_input if t.label == "Project name").input("Campus Loop Co")
    click(at, "Save settings")
    assert venture(at).name == "Campus Loop Co" and at.session_state["app_state"].dialog == ""
    assert "Campus Loop Co" in visible_text(at)


def test_staff_sees_the_directory_but_not_workspaces():
    at = sign_in("roberto")
    assert "Venture directory" in " ".join(title.value for title in at.title)
    assert "Campus Loop" in visible_text(at) and "LumaSense" in visible_text(at)
    assert not any(button.key and button.key.startswith("open_") for button in at.button)
