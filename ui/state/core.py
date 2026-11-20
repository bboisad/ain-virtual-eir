"""Core session state: who is signed in, which venture is open, which page and menu dialog are shown."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from eir import access
from eir.access import Account
from eir.coach import Coach, make_coach
from eir.filestore import FileStore, LocalFileStore, MemoryFileStore
from eir.models import Venture
from eir.repository import InMemoryRepository, JsonFileRepository, VentureRepository
from eir.seed import demo_accounts, demo_ventures

HOME = "Mentor"  # a team lands on its mentor; the briefing says what to do now (pages: ui/pages/__init__.py)


@dataclass
class AppState:
    account_id: str | None = None  # who is signed in
    venture_id: str | None = None
    page: str = HOME
    nav_round: int = 0  # counts page changes made by code (not the top navigation): see nav_key
    dialog: str = ""  # the menu dialog that is open ("" = none), see ui/menu.py
    drawer: str = ""  # the consultant whose drawer is open on the Mentor page ("" = collapsed)
    invite: str = ""  # a consultant the member asked for from the rail; the Mentor page asks the mentor next run
    rehearsal: str = ""  # the practice session open on the Practice page ("" = the Practice home)
    practice_setup: str = ""  # the setup dialog is open with these settings ("judge/pitch", see practice.Suggestion)
    saved_file: str = ""  # a file just saved on the Overview: offer to discuss it with the Virtual EIR
    upload_round: int = 0  # a new key empties the Overview's upload box after a file is saved
    discuss_file: str = ""  # a file the team chose to discuss on the Overview: the chat gives it to the Virtual EIR
    discuss_note: str = ""  # what the team wants the Virtual EIR to look at in it


@dataclass
class PageContext:
    """Everything a page needs. Pages receive this and nothing else.
    Only built for an account that is a member of the venture (see eir/access.py)."""
    account: Account
    venture: Venture
    user_id: str  # the account's member id inside this venture
    repo: VentureRepository
    coach: Coach
    files: FileStore  # project files (the venture record keeps only names, versions and summaries)

    def save(self) -> None:
        self.repo.save(self.venture)


def app_state() -> AppState:
    return st.session_state.setdefault("app_state", AppState())


# Runtime data lives outside the project folder by default: the folder may be synced (OneDrive), and demo data
# is per computer anyway. Override with EIR_DATA_DIR and EIR_FILES_DIR.
DATA_DIR = Path(os.getenv("EIR_DATA_DIR") or Path.home() / ".virtual_eir" / "ventures")
FILES_DIR = Path(os.getenv("EIR_FILES_DIR") or DATA_DIR.parent / "files")


def _storage() -> str:
    return os.getenv("EIR_STORAGE", "file")  # tests set "memory"


def repo() -> VentureRepository:
    """File storage by default: ventures survive a refresh and are shared by every browser on this computer.
    Production would swap in the instructor's database here (same interface)."""
    if "repo" not in st.session_state:
        if _storage() == "memory":
            st.session_state["repo"] = InMemoryRepository(demo_ventures())
        else:
            r = JsonFileRepository(DATA_DIR)
            if not r.list():
                for v in demo_ventures():
                    r.save(v)
            st.session_state["repo"] = r
    return st.session_state["repo"]


def filestore() -> FileStore:
    """Project files: plain files under FILES_DIR (a prototype limit), or memory for tests and the in-memory demo."""
    if "filestore" not in st.session_state:
        st.session_state["filestore"] = MemoryFileStore() if _storage() == "memory" else LocalFileStore(FILES_DIR)
    return st.session_state["filestore"]


@st.cache_resource
def _coach(provider: str, key: str, model: str, base_url: str, tools: str) -> Coach:
    return make_coach({"LLM_PROVIDER": provider, "LLM_API_KEY": key, "LLM_MODEL": model, "LLM_BASE_URL": base_url,
                       "LLM_TOOLS": tools})


def coach() -> Coach:
    def setting(name: str) -> str:
        try:
            if name in st.secrets:
                return str(st.secrets[name])
        except Exception:  # no secrets.toml
            pass
        return os.getenv(name, "")
    return _coach(*(setting(n) for n in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_TOOLS")))


# ---- sign-in (demo: pick an account; production: university sign-in) ----
def accounts() -> list[Account]:
    return access.all_accounts(demo_accounts(), repo())


def account() -> Account | None:
    s = app_state()
    return next((a for a in accounts() if a.id == s.account_id), None)


def _leave(s: AppState) -> None:
    s.venture_id, s.dialog, s.drawer, s.invite, s.rehearsal, s.practice_setup = None, "", "", "", "", ""
    s.saved_file, s.discuss_file, s.discuss_note = "", "", ""


def sign_in(account_id: str) -> None:
    s = app_state()
    _leave(s)
    s.account_id = account_id


def sign_out() -> None:
    s = app_state()
    _leave(s)
    s.account_id = None


def context() -> PageContext | None:
    """Workspace context, or None if no venture is open or the account may not open it."""
    s, acc = app_state(), account()
    if acc is None or not s.venture_id:
        return None
    v = repo().get(s.venture_id)
    if not access.can_open(acc, v):
        s.venture_id = None
        return None
    return PageContext(acc, v, access.member_in(acc, v).id, repo(), coach(), filestore())


# ---- navigation ----
def open_venture(venture_id: str, page: str = HOME) -> None:
    s = app_state()
    _leave(s)
    s.venture_id = venture_id
    go_to(page)


def leave_venture() -> None:
    _leave(app_state())


def go_to(page: str) -> None:
    """Change the page from code, e.g. "Open the Action Plan". The top navigation gets a new key (nav_key), so the
    browser draws it with this page selected: a value set on the old one was sometimes not shown when another run
    followed at once (e.g. after a dialog closed)."""
    s = app_state()
    s.page, s.dialog = page, ""
    s.nav_round += 1


def navigated(page: str) -> None:
    """The member chose a page in the top navigation, which already shows it."""
    s = app_state()
    s.page, s.dialog = page, ""


def nav_key(venture_id: str) -> str:
    return f"topnav_{venture_id}_{app_state().nav_round}"


# ---- menu dialogs: one at a time; closing is explicit or by dismissing the dialog ----
def open_dialog(name: str) -> None:
    app_state().dialog = name


def close_dialog() -> None:
    app_state().dialog = ""


def dialog() -> str:
    return app_state().dialog


# ---- the consultant drawer (Mentor page). Collapsing it never ends a consultation. ----
def drawer() -> str:
    return app_state().drawer


def open_drawer(consultant_id: str) -> None:
    app_state().drawer = consultant_id


def close_drawer() -> None:
    app_state().drawer = ""


def request_invite(consultant_id: str) -> None:
    app_state().invite = consultant_id


def pop_invite() -> str:
    s = app_state()
    consultant_id, s.invite = s.invite, ""
    return consultant_id


# ---- practice (Practice page): the open session, and the setup dialog with its pre-filled settings ----
PRACTICE = "Practice"
SETUP_KEYS = "ps_"  # widget keys of the setup dialog, cleared when it opens with new settings


def rehearsal() -> str:
    return app_state().rehearsal


def open_rehearsal(rehearsal_id: str) -> None:
    """Show a practice session (its conversation, or its feedback once it ended) on the Practice page."""
    s = app_state()
    s.rehearsal, s.practice_setup = rehearsal_id, ""
    go_to(PRACTICE)


def close_rehearsal() -> None:
    """Back to the Practice home. An unfinished session stays in progress."""
    app_state().rehearsal = ""


def practice_setup() -> str:
    return app_state().practice_setup


def open_practice_setup(settings: str) -> None:
    """Open the setup dialog on the Practice page, pre-filled ("judge/pitch", "challenger/assumption/H2")."""
    for key in [k for k in st.session_state if isinstance(k, str) and k.startswith(SETUP_KEYS)]:
        del st.session_state[key]
    s = app_state()
    s.rehearsal, s.practice_setup = "", settings
    if s.page != PRACTICE:
        go_to(PRACTICE)


def close_practice_setup() -> None:
    app_state().practice_setup = ""


# ---- project files on the Overview: save first, then the team chooses to discuss with the Virtual EIR ----
def saved_file() -> str:
    return app_state().saved_file


def file_saved(file_id: str) -> None:
    """A file was saved: empty the upload box and offer the discussion."""
    s = app_state()
    s.saved_file, s.upload_round = file_id, s.upload_round + 1


def clear_saved_file() -> None:
    app_state().saved_file = ""


def upload_round() -> int:
    return app_state().upload_round


def next_upload_round() -> None:
    app_state().upload_round += 1


def request_discussion(file_id: str, note: str = "") -> None:
    """The team chose to discuss a file (on the Overview): open the chat, where the Virtual EIR reads it and replies.
    Inside a dialog, call it in the run and then st.rerun() (a click there reruns only the dialog); go_to gives the
    top navigation a new key, so it follows."""
    s = app_state()
    s.discuss_file, s.discuss_note, s.saved_file = file_id, note.strip(), ""
    go_to(HOME)


def pop_discussion() -> tuple[str, str]:
    """The file to discuss now and the team's note ("" when none), once."""
    s = app_state()
    pending = s.discuss_file, s.discuss_note
    s.discuss_file, s.discuss_note = "", ""
    return pending


# ---- one-shot messages that must survive a rerun, e.g. "the mentor could not reply" ----
def flash(kind: str, text: str, where: str = "page") -> None:
    """kind: "error" | "success" | "info". `where`: "page", or "dialog" for a message inside the open dialog."""
    st.session_state[f"flash_{where}"] = (kind, text)


def pop_flash(where: str = "page") -> tuple[str, str] | None:
    return st.session_state.pop(f"flash_{where}", None)


def reset() -> None:
    """Back to the demo data: removes the saved ventures and their project files (file storage), and the session."""
    if _storage() != "memory":
        if DATA_DIR.exists():
            for f in DATA_DIR.glob("*.json"):
                f.unlink()
        if FILES_DIR.exists():
            for folder in FILES_DIR.iterdir():  # one folder per venture
                if folder.is_dir():
                    shutil.rmtree(folder)
    st.session_state.clear()
