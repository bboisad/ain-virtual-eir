"""Relevant old history survives context truncation without becoming evidence or crossing private boundaries."""
from datetime import datetime, timedelta, timezone

from eir import memory, recall
from eir.models import EIR, SYSTEM, Consultation, DaySummary, LeadMode, Message, MessageKind, Rehearsal
from eir.seed import demo_ventures


def campus():
    v = next(v for v in demo_ventures() if v.id == "V-CAMPUS")
    v.conversation = []
    v.day_summaries = []
    v.consultations = []
    v.rehearsals = []
    return v


def when(days=0, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)).isoformat(timespec="seconds")


def fill(v, count=32):
    for i in range(count):
        v.conversation.append(Message("m1", f"The meeting room decoration has {i} chairs.", created_at=when(minutes=i)))


def test_same_day_history_outside_the_chat_window_is_recalled_with_its_source():
    v = campus()
    old = Message("m2", "Prepayment pilot: Bob owns the interviews; deadline Friday.", created_at=when(minutes=-10))
    v.conversation.append(old)
    fill(v)
    v.conversation.append(Message("m1", "What was the deadline for the prepayment pilot?"))
    hits = memory.recalled_memories(v)
    assert len(hits) == 1 and hits[0].source_id == old.id
    assert "Bob" in hits[0].source_label and old.created_at in hits[0].source_label
    assert "deadline Friday" in hits[0].text
    messages, refs = memory.window(v)
    assert old.id not in refs.values() and "deadline Friday" not in str(messages)
    context = memory.lead_context(v)
    assert "deadline Friday" in context and "Current structured records take precedence" in context
    assert "not verified evidence" in context and "not action-tool source tags" in context


def test_the_actual_character_window_boundary_is_used_not_just_message_count():
    v = campus()
    old = Message("m1", "Prepayment deadline is Friday.")
    v.conversation = [old, Message(EIR, "Room decoration. " * 1_000),
                      Message("m1", "Room decoration. " * 1_000), Message("m1", "What is our prepayment deadline?")]
    assert old.id not in memory.window(v)[1].values()
    assert any(hit.source_id == old.id for hit in memory.recalled_memories(v))


def test_a_relevant_summary_older_than_the_last_seven_is_recalled():
    v = campus()
    day = (datetime.now(timezone.utc) - timedelta(days=20)).date().isoformat()
    v.day_summaries = [DaySummary(day, "Earlier meeting", "Library kiosk pilot begins on Friday.")]
    for i in range(8, 0, -1):
        other_day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        v.day_summaries.append(DaySummary(other_day, other_day, "The room decoration was discussed."))
    v.conversation = [Message("m1", "What did we agree about the library kiosk pilot?")]
    hits = memory.recalled_memories(v)
    assert len(hits) == 1 and hits[0].kind == "day_summary" and hits[0].source_id == day
    assert "Friday" in memory.recall_context(v)


def test_chinese_query_recalls_the_relevant_statement_without_a_word_segmenter():
    v = campus()
    old = Message("m2", "预付款实验由Bob负责，截止日期是周五。")
    v.conversation = [old]
    fill(v)
    v.conversation.append(Message("m1", "还记得之前的预付款实验截止日期吗？"))
    hits = memory.recalled_memories(v)
    assert len(hits) == 1 and hits[0].source_id == old.id
    assert "周五" in hits[0].text


def test_no_query_or_no_relevant_match_produces_no_historical_context():
    v = campus()
    assert memory.recalled_memories(v) == []
    v.conversation = [Message("m1", "The prepayment pilot starts Friday.")]
    fill(v)
    assert memory.recalled_memories(v, "What is the weather in Reykjavik?") == []
    assert memory.recalled_memories(v, "请告诉我一下我们之前的那个是什么呢") == []
    assert recall.render([]) == ""


def test_recent_messages_and_summaries_are_not_duplicated_in_the_recall_supplement():
    v = campus()
    v.conversation = [Message("m2", "Prepayment deadline is Friday."), Message("m1", "What is the prepayment deadline?")]
    day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    v.day_summaries = [DaySummary(day, "Yesterday", "Prepayment deadline is Friday.")]
    assert memory.recalled_memories(v) == []
    assert "RELEVANT EARLIER HISTORY" not in memory.lead_context(v)


def test_private_transcripts_and_non_member_messages_are_never_searched():
    v = campus()
    marker = "suppliercontract"
    v.consultations = [Consultation(consultant="pricing", messages=[Message("m1", f"{marker} secret consultant")])]
    v.rehearsals = [Rehearsal(character="customer", messages=[Message("m1", f"{marker} secret practice")])]
    v.conversation = [Message(EIR, f"{marker} assistant speculation"),
                      Message(SYSTEM, f"{marker} application note"),
                      Message("outsider", f"{marker} untrusted import"),
                      Message("m1", f"{marker} synthetic event", kind=MessageKind.EVENT)]
    fill(v)
    assert memory.recalled_memories(v, marker) == []
    assert marker not in memory.recall_context(v, marker)


def test_ip_sensitive_history_is_not_redisclosed_even_for_an_explicit_search():
    v = campus()
    v.ip_sensitive = True
    v.conversation = [Message("m1", "Secret optical formula technicalsupplier.")]
    assert recall.search(v, "technicalsupplier") == []
    assert memory.recall_context(v, "technicalsupplier") == ""


def test_retrieval_is_project_local_and_current_mentor_thread_only():
    v, other = campus(), campus()
    other.id = "V-OTHER"
    other.conversation = [Message("m1", "suppliercontract belongs to the other project.")]
    v.conversation = [Message("m1", "suppliercontract belongs to the other mentor.", mentor=LeadMode.OPTIMIZE)]
    v.day_summaries = [DaySummary("2025-01-01", "Jan 1", "suppliercontract", LeadMode.OPTIMIZE)]
    assert recall.search(v, "suppliercontract") == []
    assert len(recall.search(other, "suppliercontract")) == 1


def test_result_count_and_rendered_characters_are_bounded():
    v = campus()
    v.conversation = [Message("m1", f"Prepayment pilot revision {i}: " + "details " * 300,
                              created_at=when(minutes=i)) for i in range(12)]
    hits = recall.search(v, "prepayment pilot", limit=100)
    assert len(hits) == recall.MAX_RESULTS
    assert len(recall.render(hits)) <= recall.MAX_CHARS
    assert 0 < len(recall.render(hits, char_budget=600)) <= 600
    assert recall.render(hits, char_budget=10) == ""
    assert recall.render(hits, char_budget=-1) == ""
    assert recall.search(v, "prepayment", limit=0) == []


def test_a_recent_related_correction_is_included_before_the_old_plan():
    v = campus()
    v.conversation = [Message("m1", "The pricing experiment charges $3.", created_at=when(minutes=i))
                      for i in range(8)]
    correction = Message("m2", "Correction: the pricing experiment now charges $5; the earlier $3 plan is superseded. "
                                 "We discussed the change after learning more about customer support and processing.",
                         created_at=when(minutes=10))
    v.conversation.append(correction)
    hits = recall.search(v, "What is the price experiment?")
    assert hits[0].source_id == correction.id
    assert "$5" in hits[0].text


def test_long_excerpts_preserve_the_matching_passage_instead_of_only_the_start():
    v = campus()
    v.conversation = [Message("m1", "Unrelated background. " * 200 + "Prepayment deadline Friday. "
                              + "More background. " * 100)]
    (hit,) = recall.search(v, "prepayment deadline")
    assert "Prepayment deadline Friday" in hit.text and len(hit.text) <= recall.SNIPPET_CHARS


def test_an_application_event_does_not_reuse_a_stale_query():
    v = campus()
    v.conversation = [Message("m1", "What was the prepayment experiment?"),
                      Message("m1", "Feedback shared", kind=MessageKind.EVENT)]
    assert recall.latest_query(v) == "" and memory.recalled_memories(v) == []
