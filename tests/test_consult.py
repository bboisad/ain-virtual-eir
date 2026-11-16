"""Consultations: a brief is required, one open per consultant, the lead mentor sees only the summary,
the consultant never sees the mentor chat, and must-hand-off topics always reach a human."""
import pytest

from eir import access, actions, consult
from eir.models import EIR, ConsultationStatus, ConsultationSummary, Message
from eir.seed import demo_ventures


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


def test_brief_required_and_one_open_consultation_per_consultant():
    v = venture()
    with pytest.raises(ValueError):
        actions.invite_consultant(v, "pricing", "Is $3 supported?", "  ", EIR)
    actions.invite_consultant(v, "pricing", "Is $3 supported?", "Alice believes $3; 2 of 3 interviewees want it free.",
                              EIR)
    with pytest.raises(ValueError):
        actions.invite_consultant(v, "pricing", "Again?", "A second brief", "m1")
    actions.invite_consultant(v, "strategy", "Who else solves this?", "Facebook groups are free.", "m2")  # in parallel
    assert [r.state for r in consult.rail(v)] == ["open", "open", "unused"]
    with pytest.raises(ValueError):
        actions.invite_consultant(v, "legal", "Question", "Brief", EIR)  # no such consultant
    with pytest.raises(PermissionError):
        actions.invite_consultant(v, "funding", "Question", "Brief", "outsider")


def test_the_lead_mentor_gets_the_summary_never_the_transcript():
    v = venture()
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief: test the fee", EIR)
    actions.consult_post(v, c.id, "m1", "Our secret supplier is Bob's uncle")
    summary = ConsultationSummary(conclusions=["Free is the real competitor"], suggested_todos=["Run the prepaid test"],
                                  disagreements=["Alice still thinks $3 is fine"])
    with pytest.raises(ValueError):
        actions.end_consultation(v, c.id, "m1", summary, note="x" * 300)  # the note is one line
    actions.end_consultation(v, c.id, "m1", summary, note="I still want to try $3 first")
    view = access.lead_view_of_consultation(c)
    assert "Free is the real competitor" in view and "I still want to try $3 first" in view
    assert "secret supplier" not in view
    assert c.status == ConsultationStatus.DONE and consult.rail(v)[0].state == "done"
    with pytest.raises(ValueError):
        actions.consult_post(v, c.id, "m1", "One more thing")


def test_the_consultant_sees_the_brief_and_the_overview_but_not_the_mentor_chat():
    v = venture()
    v.conversation.append(Message("m1", "Mentor-only remark: we may drop Carol from the team"))
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief: Alice believes $3", EIR)
    view = access.consultant_view(v, c)
    assert "Brief: Alice believes $3" in view and "Sellers will pay a $3 fee per item" in view
    assert "drop Carol" not in view


def test_ip_sensitive_ventures_withhold_technical_details_from_consultants():
    luma = venture("V-LUMA")
    c = actions.invite_consultant(luma, "strategy", "Who else flags sepsis early?", "Clinical scoring is the "
                                  "alternative today.", EIR)
    view = access.consultant_view(luma, c)
    assert "IP-SENSITIVE" in view and "withheld" in view
    assert "Lab prototype" not in view  # Key Resources text is not shown


def test_must_hand_off_topics_always_reach_a_human():
    v = venture()
    c = actions.invite_consultant(v, "funding", "How much should we raise?", "Brief: an angel made an offer", EIR)
    actions.consult_post(v, c.id, "m1", "An angel sent us a term sheet for 20% of the company")
    actions.end_consultation(v, c.id, "m1", ConsultationSummary(conclusions=["Raise only what the pilot needs"]))
    assert c.summary.needs_human and c.summary.human_topic == "term sheet"


def test_topic_of_finds_the_consultant_a_message_is_about():
    assert consult.topic_of("Should our price be a subscription or a fee per item?") == "pricing"
    assert consult.topic_of("Facebook Marketplace is a competitor; how are we different?") == "strategy"
    assert consult.topic_of("Which investor or grant should we try first?") == "funding"
    assert consult.topic_of("Where do we store the items?") is None
