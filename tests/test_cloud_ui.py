"""Cloud failures and demo access are visible without exposing shared projects or losing drafts."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from eir import actions
from eir.cloud import CloudStorageError, StorageConflict
from eir.coach.scripted import ScriptedCoach
from eir.models import Message
from eir.seed import demo_ventures
from ui.state import core

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def button(at, *, key=None, label=None):
    target = at.button(key=key) if key else next(b for b in at.button if b.label == label)
    target.click().run()
    assert not at.exception


def test_cloud_mode_requires_passcode_before_any_database_access(monkeypatch):
    monkeypatch.setenv("EIR_STORAGE", "supabase")
    monkeypatch.delenv("EIR_DEMO_PASSWORD", raising=False)
    def unexpected():
        pytest.fail("Cloud data was loaded before the access gate.")
    monkeypatch.setattr(core, "repo", unexpected)
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "shared demo passcode" in at.error[0].value
    assert not at.selectbox


def test_demo_passcode_denies_wrong_value_then_unlocks_and_signout_relocks(monkeypatch):
    monkeypatch.setenv("EIR_STORAGE", "memory")
    monkeypatch.setenv("EIR_DEMO_PASSWORD", "fictional-test-passcode")
    at = AppTest.from_file(APP, default_timeout=20).run()
    assert not at.exception and not at.selectbox
    at.text_input(key="demo_access_password").set_value("incorrect")
    button(at, label="Open demo")
    assert at.error and not at.selectbox
    at.text_input(key="demo_access_password").set_value("fictional-test-passcode")
    button(at, label="Open demo")
    assert at.selectbox and not at.exception
    assert "demo_access_password" not in at.session_state
    button(at, label="Sign in")
    button(at, label="Sign out")
    assert at.text_input(key="demo_access_password") and not at.selectbox


def test_cloud_configuration_failure_never_falls_back_to_local_storage(monkeypatch):
    monkeypatch.setenv("EIR_STORAGE", "supabase")
    monkeypatch.setenv("EIR_DEMO_PASSWORD", "fictional-test-passcode")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.text_input(key="demo_access_password").set_value("fictional-test-passcode")
    button(at, label="Open demo")
    assert any("SUPABASE_URL" in error.value for error in at.error)
    assert "repo" not in at.session_state


def test_cloud_reset_is_rejected_before_touching_local_files(monkeypatch, tmp_path):
    marker = tmp_path / "venture.json"
    marker.write_text("keep")
    monkeypatch.setattr(core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(core, "cloud_storage", lambda: True)
    with pytest.raises(CloudStorageError):
        core.reset()
    assert marker.read_text() == "keep"


def test_failed_cloud_save_keeps_a_downloadable_draft_and_stops_the_success_flow():
    source = '''
import streamlit as st
from eir.cloud import StorageConflict
from eir.seed import demo_ventures
from ui.state.core import PageContext
class StaleRepository:
    def save(self, venture):
        raise StorageConflict("A teammate saved first")
v = demo_ventures()[0]
v.description = "My unsaved team decision"
ctx = PageContext(None, v, "m1", StaleRepository(), None, None)
ctx.save()
st.success("Should never reach this")
'''
    at = AppTest.from_string(source).run()
    assert not at.exception and not at.success
    assert at.session_state["unsaved_work"][0]["description"] == "My unsaved team decision"
    assert at.session_state["unsaved_work"][1] is True
    assert any("teammate saved" in w.value for w in at.warning)
    assert at.get("download_button")


def test_project_memory_dialog_searches_and_attributes_team_history(monkeypatch):
    monkeypatch.setenv("EIR_STORAGE", "memory")
    monkeypatch.delenv("EIR_DEMO_PASSWORD", raising=False)
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.selectbox[0].set_value("alice").run()
    button(at, label="Sign in")
    button(at, key="open_V-CAMPUS")
    v = at.session_state["repo"].get("V-CAMPUS")
    statement = "The library kiosk experiment is owned by Bob: $36 ... $3, **literal** [Markdown](terms)."
    v.conversation.append(Message("m2", statement))
    button(at, key="menu_memory")
    at.text_input(key="memory_search_V-CAMPUS").set_value("library kiosk").run()
    assert not at.exception
    assert any(t.value == statement for t in at.text)
    assert v.conversation[-1].text == statement
    assert any("Bob" in c.value and "Team message" in c.value for c in at.caption)


def test_scripted_demo_can_recall_real_saved_history_without_a_model():
    v = next(v for v in demo_ventures() if v.id == "V-CAMPUS")
    v.conversation = [Message("m2", "The library kiosk experiment starts Friday.")]
    reply = actions.mentor_message(v, ScriptedCoach(), "m1", "Do you remember our library kiosk experiment?")
    assert "Friday" in reply.text and "Bob" in reply.text
    assert not reply.change_groups


def test_unsaved_project_export_is_hidden_from_a_different_account():
    source = '''
import streamlit as st
from eir.cloud import StorageConflict
from eir.seed import demo_ventures
from ui.state.core import app_state, keep_unsaved, render_unsaved
app_state().account_id = "staff"
keep_unsaved(demo_ventures()[0], StorageConflict("changed"), "alice")
render_unsaved()
st.success("Staff sees no founder draft")
'''
    at = AppTest.from_string(source).run()
    assert not at.exception and at.success
    assert not at.get("download_button") and not at.warning


def test_create_retry_preserves_form_and_confirms_an_uncertain_save_without_duplicates():
    source = '''
import streamlit as st
from eir.access import Account, Role
from eir.cloud import CloudStorageError
from eir.models import Stage, VentureType, LeadMode, Traction, Goal
from ui.lobby import _create_workspace
class UncertainRepository:
    def __init__(self):
        self.items = {}
        self.saves = 0
    def get(self, vid):
        return self.items[vid]
    def save(self, v):
        self.items[v.id] = v
        self.saves += 1
        raise CloudStorageError("Response was lost")
if "repo" not in st.session_state:
    st.session_state["repo"] = UncertainRepository()
prefix = "create_test"
if "initialized" not in st.session_state:
    st.session_state["initialized"] = True
    st.session_state[prefix + "_pending"] = dict(name="Lab Share", description="Shared lab space", background="Other",
        stage=Stage.IDEA, type=VentureType.MARKET, ip=False, traction=Traction.NO, goal=Goal.LAUNCH)
st.button("Create", on_click=_create_workspace, args=(Account("alice", "Alice Chen", Role.FOUNDER), prefix, LeadMode.LAUNCH))
'''
    # Use actual enum names from the app so this test follows the user-visible create flow.
    from eir.models import Goal, Traction
    source = source.replace("Traction.NO", f"Traction.{list(Traction)[0].name}")
    source = source.replace("Goal.LAUNCH", f"Goal.{list(Goal)[0].name}")
    at = AppTest.from_string(source).run()
    assert not at.exception
    button(at, label="Create")
    assert "create_test_pending" in at.session_state
    draft = at.session_state["create_test_draft"]
    assert len(at.session_state["repo"].items) == 1
    button(at, label="Create")
    assert at.session_state["app_state"].venture_id == draft.id
    assert at.session_state["repo"].saves == 1
    assert "create_test_pending" not in at.session_state
