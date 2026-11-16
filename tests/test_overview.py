"""Overview: what are we doing, where are we stuck, what next? The focus card (every line but the focus is a rule),
progress in words, the snapshot, the start page of a new project, the history, and the preliminary project plan."""
from eir import actions, overview, records, roadmap, teams
from eir.access import Account
from eir.coach.scripted import ScriptedCoach
from eir.models import (CANVAS_BLOCKS, EIR, RUNG_NAMES, ConsultationSummary, Direction, Experiment, LeadMode,
                        NextStep, Rung)
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


def test_the_focus_card_says_why_now_what_is_known_what_is_missing_and_the_next_step():
    v = campus()
    c = overview.focus_card(v)
    assert c.question == "Will sellers really pay $3 per item?" and c.why.startswith('Rated "fatal if wrong"')
    assert (c.known.text, c.known.rung) == ("Alice believes students will happily pay $3 per item", Rung.ASSERTION)
    assert (c.against.rung, c.against.source) == (Rung.SAID, "Bob · Oct 5")  # each side keeps its own level
    assert c.missing == "No one has acted on it yet (signed up, tried, paid)" and c.owner == "your Virtual EIR"
    assert isinstance(c.next, Experiment) and c.next.id == "X-fee" and c.cta == "start"  # a draft: review and start
    actions.start_experiment(v, "X-fee", "m1")
    assert overview.focus_card(v).cta == "result"
    v.experiments, v.next_steps = [], []
    assert overview.focus_card(v).next is None and overview.focus_card(v).cta == "chat"


def test_a_key_question_focus_says_which_step_needs_it_and_what_it_needs():
    v = campus()
    records.set_focus(v, "Has anyone committed?", "question", "pd_commitment", by="m2")
    c, q = overview.focus_card(v), roadmap.question("pd_commitment")
    assert c.why == "Needed to finish Pitch deck" and c.owner == "Bob" and c.against is None
    assert c.missing == ("" if v.answer(q.id).rung >= q.need else
                         f"Needs {RUNG_NAMES[q.need].lower()} (level {int(q.need)})")


def test_progress_is_the_four_deliverables_and_the_question_to_answer_now():
    v = campus()
    assert [(s.title, s.state) for s in overview.steps(v)] == [
        ("Customer discovery", "done"), ("Business model canvas", "done"), ("Pitch deck", "now"),
        ("Business plan", "later")]
    assert overview.current_question(v).id == "pd_dmu"  # the first one without enough evidence
    records.set_focus(v, "Has anyone committed?", "question", "pd_commitment", by=EIR)
    assert overview.current_question(v).id == "pd_commitment"  # the focus, when it is one of this step's questions


def test_a_project_nobody_has_worked_on_gets_a_start_page():
    v = teams.create_workspace(InMemoryRepository([]), Account("dana", "Dana Wu"), "Pilot", "Delivery")
    assert overview.is_new(v) and not overview.is_new(campus())
    assert overview.current_question(v).ask == overview.focus_card(v).question  # one question on the page, not two
    actions.mentor_message(v, ScriptedCoach(), v.members[0].id, "We want to help grad students share lab gear.")
    assert not overview.is_new(v)


def test_recent_activity_includes_the_timeline_after_the_changes_of_the_same_day():
    v = campus()
    assert [r.text for r in overview.recent_changes(v, 3, events=True)] == [
        "Moved from M1 · Business Model Canvas to M2 · The Perfect Pitch",
        "AIN staff (demo) confirmed: Business Model Canvas complete",
        "Residence Life approved tabling at move-out week"]
    records.add_evidence(v, "H2", "4 of 5 want it free", Direction.AGAINST, Rung.SAID, by=EIR)
    assert "evidence against" in overview.recent_changes(v, 1, events=True)[0].text  # made today: it comes first


def test_the_history_lists_the_decisions_newest_first():
    assert [e.text for e in overview.decisions(campus())] == ["Test the $3 fee instead of debating it",
                                                              "Interview movers before building anything"]


def test_students_see_plain_evidence_names_and_the_model_keeps_its_labels():
    assert Rung.SAID.plain == "Customer statements · Level 3" and Rung.NONE.plain == "Not graded yet"
    assert Rung.SAID.label == "3 · Customers said"  # prompts and evaluation read this one


def test_suggestions_say_who_set_them():
    v = campus()
    assert overview.focus_owner(v) == "your Virtual EIR"
    records.set_focus(v, "Who pays?", "assumption", "H2", by="m2")
    assert overview.focus_owner(v) == "Bob" and overview.set_by(v, "nobody") == ""


def test_the_core_cards_keep_the_teams_words_apart_from_the_graded_records():
    v = campus()
    items = overview.essentials(v)
    assert [i.field for i in items] == ["customer", "solution", "revenue"]
    assert items[0].text == v.profile.customer and items[0].record_name == "Customer Segments"
    assert items[0].source == "Team · Sep 28 session"  # who wrote the record, for "where it comes from"
    assert items[0].rung == v.canvas["Customer Segments"].rung and items[2].record_text == "$3 fee per item sold"
    v.lead_mode = LeadMode.OPTIMIZE
    records.grade_lens(v, "business_model", Rung.SAID, "Sellers say $3 is fine", "3 interviews", by=EIR)
    revenue = overview.essentials(v)[2]
    assert revenue.record_name == "Business model lens" and revenue.rung == Rung.SAID
    assert overview.essentials(v)[0].record_name == "Customer Segments"  # an ungraded lens falls back to the canvas


def test_status_shows_the_focus_the_position_and_the_step_progress():
    v = campus()
    st = overview.status(v)
    assert st.focus == "Will sellers really pay $3 per item?" and st.focus_rung == Rung.SAID
    assert st.position.startswith("M2 · Pitch deck · step ")
    assert st.progress.endswith("key questions have enough evidence") and st.deliverable_id == "pitch_deck"


def test_the_position_follows_a_focused_key_question():
    v = campus()
    records.set_focus(v, "Has anyone committed?", "question", "pd_commitment", by=EIR)
    assert overview.status(v).position == "M2 · Pitch deck · step 23 Show the dogs will eat the dog food"
    records.set_focus(v, "Which legal structure?", "question", "pd_legal", by=EIR)
    assert overview.status(v).position == "M2 · Pitch deck · Foundry item"


def test_at_most_three_next_actions_with_the_focus_experiment_first():
    v = campus()
    for i in range(4):
        records.add_task(v, f"Task {i}", "team", by=EIR, due_date=f"2026-11-1{i}")
    items = overview.next_actions(v)
    assert len(items) == 3 and isinstance(items[0], Experiment) and items[0].id == "X-fee"
    assert not any(isinstance(i, NextStep) and i.id == "S2" for i in items)  # S2 is shown through its experiment


def test_key_assumptions_rank_open_ones_by_importance_then_weakest_evidence():
    assert [h.id for h in overview.key_assumptions(campus())] == ["H2", "H1", "H3"]


def test_recent_changes_include_mentor_updates_and_consultations():
    v = campus()
    records.add_evidence(v, "H2", "4 of 5 want it free", Direction.AGAINST, Rung.SAID, by=EIR)
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief", EIR)
    actions.end_consultation(v, c.id, "m1", ConsultationSummary(conclusions=["Free is the competitor"]))
    texts = [r.text for r in overview.recent_changes(v)]
    assert any(t.startswith("Pricing & business model consultant reviewed") for t in texts)
    assert any("evidence against" in t for t in texts) and len(texts) <= overview.MAX_CHANGES


def test_the_evidence_map_and_status_follow_the_lead_mentor():
    v = campus()
    assert [e.name for e in overview.evidence_map(v)] == list(CANVAS_BLOCKS)
    v.lead_mode = LeadMode.OPTIMIZE
    assert [e.name for e in overview.evidence_map(v)] == ["Problem", "Customer", "Solution", "Market",
                                                          "Business model", "Advantage"]
    st = overview.status(v)
    assert st.position == "Bottleneck: not found yet" and st.progress == "0 of 6 lenses graded"


def test_the_preliminary_project_plan_has_every_section():
    plan = overview.preliminary_plan(campus(), today_iso="2026-11-06")
    for heading in ("## Problem", "## First customer (beachhead)", "## Value proposition", "## Business model canvas",
                    "## The 3 riskiest assumptions", "## Next 30 days"):
        assert heading in plan
    assert "Sellers will pay a $3 fee per item" in plan and "4 · Customers did" in plan
