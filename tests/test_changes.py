"""The mentor's record updates are logged and can be undone per action; members' own edits are not undone this way."""
import pytest

from eir import actions, changes, records
from eir.models import EIR, Direction, Importance, RecordKind, Rung, Venture
from eir.seed import demo_ventures
from eir.serde import from_dict, to_dict


def campus():
    return next(v for v in demo_ventures() if v.id == "V-CAMPUS")


def test_mentor_update_is_logged_and_undo_restores_it():
    v = campus()
    group = changes.new_group()
    records.add_evidence(v, "H2", "4 of 5 interviewees would only use it if free", Direction.AGAINST, Rung.SAID,
                         by=EIR, group=group, source="message m12")
    (c,) = changes.changes_in(v, group)
    assert c.kind == RecordKind.ASSUMPTION and c.record_id == "H2" and c.by == EIR and "evidence against" in c.summary
    assert len(v.hypothesis("H2").evidence_items) == 3
    actions.undo(v, group, "m2")
    assert len(v.hypothesis("H2").evidence_items) == 2 and c.undone_by == "m2"
    with pytest.raises(ValueError):
        actions.undo(v, group, "m2")  # nothing left to undo


def test_one_mentor_action_is_undone_as_a_whole():
    v = campus()
    group = changes.new_group()
    h = records.add_assumption(v, "Buyers will pay a small fee instead", by=EIR, group=group)
    records.set_focus(v, "Who pays: buyers or sellers?", "assumption", h.id, by=EIR, group=group)
    assert v.focus.ref == h.id
    actions.undo(v, group, "m1")
    assert v.hypothesis(h.id) is None and v.focus.ref == "H2"


def test_undo_is_refused_when_the_record_changed_since():
    v = campus()
    group = changes.new_group()
    records.update_assumption(v, "H2", by=EIR, importance=Importance.HIGH, group=group)
    actions.edit_assumption(v, "H2", "Sellers will pay $2 per item", "m1")  # a member edited it afterwards
    assert isinstance(changes.undo_problem(v, group), ValueError)
    with pytest.raises(ValueError):
        actions.undo(v, group, "m1")
    assert v.hypothesis("H2").statement == "Sellers will pay $2 per item"


def test_members_cannot_undo_their_own_edits_this_way_and_outsiders_cannot_undo():
    v = campus()
    actions.edit_assumption(v, "H1", "Movers have bulky items they cannot sell easily", "m1")
    with pytest.raises(PermissionError):
        actions.undo(v, v.changes[-1].group, "m1")
    group = changes.new_group()
    records.set_status(v, "H1", "Testing", by=EIR, group=group)
    with pytest.raises(PermissionError):
        actions.undo(v, group, "outsider")


def test_assumption_numbers_are_never_reused_after_an_undo():
    v = campus()
    group = changes.new_group()
    first = records.add_assumption(v, "A", by=EIR, group=group)
    actions.undo(v, group, "m1")
    second = records.add_assumption(v, "B", by=EIR)
    assert (first.id, second.id) == ("H4", "H5")


def test_the_change_log_survives_a_save_and_undo_still_works():
    v = campus()
    records.set_focus(v, "Who decides on the purchase?", "question", "pd_dmu", by=EIR)
    again = from_dict(Venture, to_dict(v))
    assert again.changes[-1].after["ref"] == "pd_dmu"
    actions.undo(again, again.changes[-1].group, "m1")
    assert again.focus.ref == "H2"
