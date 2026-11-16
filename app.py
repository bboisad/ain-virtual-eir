"""AIN Virtual EIR — Streamlit entry point.  Run: streamlit run app.py

Wiring only. Domain logic lives in eir/, screens in ui/. See docs/ARCHITECTURE.md.
Routing: not signed in → login · AIN staff → directory · founder → own ventures → workspace
(top bar: Mentor · Overview · Action Plan, and the ⋯ menu with its dialogs).
"""
import streamlit as st

from eir.access import Role
from eir.cloud import CloudStorageError
from ui import lobby, login, menu, staff, state, topbar
from ui.components import inject_css
from ui.pages import BY_TITLE

st.set_page_config(page_title="AIN Virtual EIR", page_icon="🌱", layout="wide", initial_sidebar_state="collapsed")
inject_css()

try:
    state.require_demo_access()
    state.render_unsaved()
    account = state.account()
    ctx = state.context()
    if account is None:
        login.render()
    elif account.role == Role.STAFF:
        staff.render(account)
    elif ctx is None:
        lobby.render(account)
    else:
        if state.app_state().page not in BY_TITLE:
            state.go_to(state.HOME)
        topbar.render(ctx)
        BY_TITLE[state.app_state().page].render(ctx)
        menu.render_dialog(ctx)
except CloudStorageError as err:
    st.error(str(err))
    st.info("The cloud connection needs attention. Your project was not moved to temporary local storage.")
    st.button("Try the connection again", on_click=st.rerun)
