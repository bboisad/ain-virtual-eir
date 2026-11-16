"""The top bar of a workspace: venture and lead mentor, the three pages, and the ⋯ menu."""
from __future__ import annotations

from html import escape

import streamlit as st

from eir import modes
from ui import menu, state
from ui.pages import PAGES

ICONS = {p.title: p.icon for p in PAGES}


def render(ctx: state.PageContext) -> None:
    v = ctx.venture
    with st.container(key="topbar"):
        name, nav, more = st.columns([3, 4, 1], vertical_alignment="center")
        name.markdown(f"<div class='eyebrow'>AIN · Virtual EIR</div><div class='venture-name'>{escape(v.name)}</div>"
                      f"<div class='muted'>{escape(modes.NAMES[v.lead_mode])} · AI</div>", unsafe_allow_html=True)
        with nav:
            _navigation(ctx)
        with more:
            menu.render_menu(ctx)


def _navigation(ctx: state.PageContext) -> None:
    """A segmented control kept in step with the current page. Code can change the page too (e.g. "Open the Action
    Plan"): then the control has a new key (state.nav_key), so it is drawn anew with that page selected."""
    key = state.nav_key(ctx.venture.id)
    if key not in st.session_state:
        st.session_state[key] = state.app_state().page
    st.segmented_control("Pages", [p.title for p in PAGES], key=key, required=True, label_visibility="collapsed",
                         format_func=lambda title: f"{ICONS[title]} {'Virtual EIR' if title == state.HOME else title}",
                         on_change=_navigate, args=(key,))


def _navigate(key: str) -> None:
    page = st.session_state.get(key)
    if page:
        state.navigated(page)
