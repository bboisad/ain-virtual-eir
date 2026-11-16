"""Confidentiality rules (client kickoff + design doc F11)."""
import pytest

from eir import access, actions, brief, teams
from eir.access import Account, Role
from eir.repository import InMemoryRepository
from eir.seed import demo_accounts, demo_ventures

ALICE = Account("alice", "Alice Chen")
PRIYA = Account("priya", "Priya Raman")
STAFF = Account("roberto", "AIN staff", Role.STAFF)


def repo():
    return InMemoryRepository(demo_ventures())


def test_founders_only_see_their_own_venture():
    r = repo()
    assert [v.name for v in access.visible_ventures(ALICE, r)] == ["Campus Loop"]
    assert [v.name for v in access.visible_ventures(PRIYA, r)] == ["LumaSense"]
    assert access.visible_ventures(Account("nobody", "No One"), r) == []


def test_founder_cannot_open_another_teams_workspace():
    luma = repo().get("V-LUMA")
    assert not access.can_open(ALICE, luma)
    with pytest.raises(PermissionError):
        access.member_in(ALICE, luma)


def test_staff_cannot_open_workspaces_and_only_read_shared_briefs():
    r = repo()
    campus = r.get("V-CAMPUS")
    assert not access.can_open(STAFF, campus) and access.visible_ventures(STAFF, r) == []
    assert access.shared_briefs_for_staff(STAFF, campus) == []

    actions.share_brief(campus, "Pricing", brief.mentor_brief(campus, "Pricing"), "m1")
    shared = access.shared_briefs_for_staff(STAFF, campus)
    assert len(shared) == 1 and "Evidence so far" in shared[0].text
    entry = next(e for e in access.staff_directory(STAFF, r) if e.venture_id == "V-CAMPUS")
    assert entry.help_requested and entry.shared_brief_count == 1


def test_founder_cannot_use_staff_views():
    with pytest.raises(PermissionError):
        access.staff_directory(ALICE, repo())


def test_new_venture_is_visible_to_its_creator_and_teammates_only():
    r = repo()
    v = teams.create_workspace(r, Account("dana", "Dana Wu"), "Test Co", "")
    teams.join_venture(v, Account("eli", "Eli Park"))
    r.save(v)
    assert access.can_open(Account("dana", "Dana Wu"), v) and access.can_open(Account("eli", "Eli Park"), v)
    assert not access.can_open(ALICE, v)
    assert {a.id for a in access.all_accounts(demo_accounts(), r)} >= {"dana", "eli", "roberto"}


def test_ip_sensitive_venture_is_flagged_to_the_llm_and_in_briefs():
    from eir import memory
    luma = repo().get("V-LUMA")
    assert "IP-SENSITIVE" in memory.lead_context(luma)
    assert "no technical details" in brief.mentor_brief(luma, "IP")


def test_only_members_talk_to_the_mentor_and_each_message_keeps_its_author():
    from eir.coach.scripted import ScriptedCoach
    v = repo().get("V-CAMPUS")
    with pytest.raises(PermissionError):
        actions.mentor_message(v, ScriptedCoach(), "stranger", "hi")
    with pytest.raises(ValueError):
        actions.mentor_message(v, ScriptedCoach(), "m3", "  ")
    assert not v.conversation
    actions.mentor_message(v, ScriptedCoach(), "m3", "hi")
    assert [m.author for m in v.conversation] == ["m3", "eir"]
