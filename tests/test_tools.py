"""The lead mentor's actions: every write cites a team message, mode-specific actions, failed calls change nothing,
a failed turn rolls back, and there is no action that completes a Foundry step."""
from eir import changes, consult, files
from eir.filestore import MemoryFileStore
from eir.llm import ToolCall
from eir.models import LeadMode, Message, Rung
from eir.seed import demo_ventures
from eir.tools import READ_ONLY, TOOLS, ToolBox


def box_with_message(text="We did 5 interviews; 4 of 5 want it free", mode=LeadMode.LAUNCH):
    v = next(x for x in demo_ventures() if x.id == "V-CAMPUS")
    v.lead_mode = mode
    msg = Message("m2", text, mentor=mode)
    v.conversation.append(msg)
    return v, ToolBox(v, refs={"m1": msg.id})


def run(box, name, **args):
    return box.call(ToolCall("t", name, args))


def test_a_write_must_cite_a_team_message():
    v, box = box_with_message()
    before = len(v.hypothesis("H2").evidence_items)
    for source in ("", "m9"):
        result = run(box, "add_evidence", assumption_id="H2", text="4 of 5 want it free", direction="against",
                     rung=3, source=source)
        assert result.startswith("ERROR: source")
    assert len(v.hypothesis("H2").evidence_items) == before and not box.groups
    assert not run(box, "add_evidence", assumption_id="H2", text="4 of 5 want it free", direction="against", rung=3,
                   source="m1").startswith("ERROR")
    (group,) = box.groups
    assert changes.changes_in(v, group)[0].source == f"message {v.conversation[-1].id}"


def test_invalid_arguments_change_nothing():
    v, box = box_with_message()
    assert run(box, "add_evidence", assumption_id="H2", text="x", direction="unclear", rung=3, source="m1") \
        .startswith("ERROR: direction")
    assert run(box, "add_evidence", assumption_id="H2", text="x", direction="for", rung=9, source="m1") \
        .startswith("ERROR: rung")
    assert run(box, "add_assumption", statement="x", importance="high", source="m1").startswith("ERROR")
    assert run(box, "add_task", text="Call", owner="Zed", source="m1").startswith("ERROR: owner")
    assert not box.groups and not v.changes


def test_actions_follow_the_lead_mentor():
    _, launch = box_with_message()
    names = {s.name for s in launch.specs()}
    assert {"record_answer", "update_canvas"} <= names and not {"grade_lens", "set_bottleneck"} & names
    assert run(launch, "grade_lens", lens="problem", rung=3, summary="", source="m1").startswith("ERROR: there is no")
    _, optimize = box_with_message(mode=LeadMode.OPTIMIZE)
    names = {s.name for s in optimize.specs()}
    assert {"grade_lens", "set_bottleneck"} <= names and not {"record_answer", "update_canvas"} & names


def test_no_action_completes_a_step_moves_the_module_or_edits_documents():
    for name, tool in TOOLS.items():
        assert not any(word in name for word in ("step", "module", "graduat")), name
        if any(word in name for word in ("document", "file")):
            assert name in READ_ONLY, name  # the mentor reads the team's documents, never edits them
        assert tool.spec.parameters["type"] == "object" and tool.spec.description


def test_the_mentor_reads_files_in_parts_without_changing_anything():
    v, _ = box_with_message()
    store = MemoryFileStore()
    f, _, _ = files.add_version(v, store, "Interview notes.md", ("x" * 9000 + " the end").encode(), "m2")
    assert "read_file" not in {s.name for s in ToolBox(v).specs()}  # no store: no reading
    box = ToolBox(v, refs={"m1": v.conversation[-1].id}, files=store)
    assert "read_file" in {s.name for s in box.specs()}
    first, second = run(box, "read_file", file_id=f.id), run(box, "read_file", file_id=f.id, part=2)
    assert first.startswith("Interview notes.md, version 1, part 1 of 2") and second.endswith("the end")
    assert run(box, "read_file", file_id="F-nope").startswith("ERROR")
    assert not box.groups and not v.changes
    assert run(box, "add_task", text="Add who said it", file_id=f.id, source="m1").endswith("Interview notes.md")
    assert files.revision_tasks(v, f)[0].text == "Add who said it"


def test_owner_by_first_name_and_one_group_per_call():
    v, box = box_with_message()
    run(box, "add_task", text="Plan the pilot", owner="Carol", source="m1")
    run(box, "set_focus", text="Who pays?", kind="assumption", ref="H2", source="m1")
    assert len(box.groups) == 2 and v.next_steps[-1].owner == "m3"


def test_rollback_undoes_the_whole_turn_and_removes_opened_consultations():
    v, box = box_with_message()
    run(box, "add_assumption", statement="Buyers will pay instead", importance=3, source="m1")
    run(box, "open_consultation", consultant="pricing", question="Is $3 supported?", brief="Brief")
    assert v.hypothesis("H4") and consult.open_consultations(v)
    box.rollback()
    assert v.hypothesis("H4") is None and not consult.open_consultations(v) and not v.changes


def test_consultation_sources_need_a_returned_summary_and_optimize_is_suggested_once():
    v, box = box_with_message()
    run(box, "open_consultation", consultant="pricing", question="Is $3 supported?", brief="Brief")
    cid = box.opened[0]
    assert run(box, "add_task", text="Run the prepaid test", source=f"consult:{cid}").startswith("ERROR: source")
    assert run(box, "suggest_mode_switch", to="Optimize", reason="paying customers").startswith("The team will see")
    assert run(box, "suggest_mode_switch", to="Optimize", reason="again").startswith("ERROR")
    assert box.suggested_mode == LeadMode.OPTIMIZE


def test_a_record_answer_is_graded_and_tracked():
    v, box = box_with_message("6 of 15 movers paid $3 at the table")
    assert not run(box, "record_answer", question_id="pd_commitment", text="6 of 15 movers paid $3", rung=5,
                   source="m1").startswith("ERROR")
    assert v.answer("pd_commitment").rung == Rung.PAID
    changes.undo_group(v, box.groups[0], "eir")
    assert v.answer("pd_commitment").rung == Rung.ASSERTION
