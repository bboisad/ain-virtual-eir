from copy import deepcopy

import pytest

from eir.access import Account, Role, can_open, visible_ventures
from eir.models import Stage, VentureType
from eir.repository import InMemoryRepository
from eir.seed import demo_ventures
from eir.serde import to_dict
from eir.teams import (create_workspace, find_invited_venture, invitation_code,
                       join_venture, save_project_details, save_project_essentials, save_project_intro)


def test_the_team_writes_and_confirms_its_project_intro_and_core_content():
    v = next(x for x in demo_ventures() if x.id == "V-CAMPUS")
    v.profile.notes["revenue"] = "Still an assumption"
    records = (to_dict(v.canvas), to_dict(v.hypotheses), to_dict(v.answers))
    save_project_intro(v, "m2", name=" Campus Loop ", one_liner="  Sell bulky   dorm items at move-out ",
                       customer="Students moving out with bulky items", problem="Selling bulky items is a hassle")
    assert (v.name, v.description, v.profile.one_liner) == ("Campus Loop", "Sell bulky dorm items at move-out",
                                                            "Sell bulky dorm items at move-out")
    assert v.profile.completed_by == "m2" and v.profile.problem == "Selling bulky items is a hassle"
    save_project_essentials(v, "m1", revenue="A $1 pickup fee paid by buyers")
    assert v.profile.revenue == "A $1 pickup fee paid by buyers" and "revenue" not in v.profile.notes
    assert v.profile.customer == "Students moving out with bulky items" and v.profile.completed_by == "m1"
    assert (to_dict(v.canvas), to_dict(v.hypotheses), to_dict(v.answers)) == records  # never evidence
    events = len(v.timeline)
    save_project_essentials(v, "m3", revenue="A $1 pickup fee paid by buyers")  # nothing changed
    assert len(v.timeline) == events and v.profile.completed_by == "m1"
    with pytest.raises(PermissionError):
        save_project_essentials(v, "outsider", revenue="Free")
    with pytest.raises(ValueError):
        save_project_intro(v, "m1", name=" ", one_liner="", customer="", problem="")


def test_create_has_only_creator_and_opens_without_intake():
    repo = InMemoryRepository([])
    alice = Account("university-alice-01", "Alice Smith")
    v = create_workspace(repo, alice, " Pilot ", " Campus delivery ", " Will people pay? ")
    assert v.name == "Pilot"
    assert len(v.members) == 1
    assert v.members[0].account == alice.id
    assert v.profile.need == "Will people pay?"
    assert can_open(alice, v)
    assert v.timeline[-1].by == v.members[0].id


def test_invitation_preview_does_not_join_and_acceptance_is_explicit_idempotent():
    repo = InMemoryRepository([])
    owner, joiner = Account("alice-01", "Alice Smith"), Account("bob-02", "Bob Lee")
    v = create_workspace(repo, owner, "Pilot", "Delivery")
    code = invitation_code(v)
    assert invitation_code(deepcopy(v)) == code
    assert find_invited_venture(repo, f" {code.lower()} ") is v
    assert visible_ventures(joiner, repo) == []
    assert find_invited_venture(repo, "wrong-code") is None
    joined = join_venture(v, joiner, "Master's student")
    assert can_open(joiner, v)
    assert joined.account == joiner.id
    assert join_venture(v, joiner) is joined
    assert len(v.members) == 2
    assert len(v.timeline) == 2


def test_same_first_name_does_not_merge_accounts_or_members():
    repo = InMemoryRepository([])
    first, second = Account("alice-01", "Alice Smith"), Account("alice-02", "Alice Jones")
    v = create_workspace(repo, first, "Pilot", "Delivery")
    joined = join_venture(v, second)
    assert v.members[0].id != joined.id
    assert v.member_for_account(first.id).name == first.name
    assert v.member_for_account(second.id).name == second.name


def test_staff_cannot_create_or_join_project():
    repo = InMemoryRepository([])
    staff = Account("staff-01", "Staff", Role.STAFF)
    v = create_workspace(repo, Account("alice-01", "Alice Smith"), "Pilot", "Delivery")
    with pytest.raises(PermissionError):
        create_workspace(repo, staff, "Private", "")
    with pytest.raises(PermissionError):
        join_venture(v, staff)
    assert len(v.members) == 1


def test_project_settings_are_attributed_and_never_become_canvas_evidence():
    repo = InMemoryRepository([])
    v = create_workspace(repo, Account("alice-01", "Alice Smith"), "Pilot", "Delivery")
    before_canvas, by = deepcopy(v.canvas), v.members[0].id
    save_project_details(v, by, " Pilot 2 ", "Updated description", Stage.MVP, VentureType.MARKET, True)
    assert (v.name, v.description, v.stage, v.ip_sensitive) == ("Pilot 2", "Updated description", Stage.MVP, True)
    assert v.timeline[-1].by == by
    assert v.canvas == before_canvas
    with pytest.raises(PermissionError):
        save_project_details(v, "outsider", "Pilot", "", Stage.IDEA, VentureType.MARKET, False)
    with pytest.raises(ValueError):
        save_project_details(v, by, " ", "", Stage.IDEA, VentureType.MARKET, False)


def test_new_project_records_the_two_questions_and_the_chosen_mentor():
    from eir.models import Goal, LeadMode, Traction
    repo = InMemoryRepository([])
    v = create_workspace(repo, Account("alice-01", "Alice Smith"), "Pilot", "Delivery", lead_mode=LeadMode.LAUNCH,
                         traction=Traction.YES, goal=Goal.IMPROVE)
    c = v.mode_choice
    assert (c.traction, c.goal, c.recommended, c.chosen) == (Traction.YES, Goal.IMPROVE, LeadMode.OPTIMIZE,
                                                             LeadMode.LAUNCH)
    assert v.lead_mode == LeadMode.LAUNCH and c.by == v.members[0].id
