"""A founder's projects; creating one in two steps (two questions, then the team picks its lead mentor with the
system's recommendation); and explicit invitation acceptance."""
from __future__ import annotations

from html import escape

import streamlit as st

from eir import access, modes, overview, teams
from eir.models import BACKGROUNDS, Goal, LeadMode, Stage, Traction, VentureType
from ui import state
from ui.components import chip, chips, md


def render(account: access.Account) -> None:
    st.markdown("<div class='eyebrow'>AIN Center · Virtual Entrepreneur in Residence (Virtual EIR)</div>",
                unsafe_allow_html=True)
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    a.title("My projects")
    b.button("Sign out", icon=":material/logout:", width="stretch", on_click=state.sign_out)
    st.write(f"Signed in as **{account.name}** · Account ID: `{account.id}`")
    st.caption("Prototype: demo data is fictional and saved on this computer. To try joining as a teammate, sign out "
               "and choose another demo account in the same tab.")
    ventures = access.visible_ventures(account, state.repo())
    if not ventures:
        st.info("Create a project or join one with an invitation code to begin.")
    for v in ventures:
        with st.container(border=True):
            a, b = st.columns([5, 1], vertical_alignment="center")
            with a:
                st.markdown(f"#### {escape(v.name)}")
                chips(chip(modes.NAMES[v.lead_mode]), chip(v.type.value), chip(f"{len(v.members)} members"))
                st.write(md(v.description) if v.description else "Project description can be added later.")
                st.caption("Current focus: " + md(overview.status(v).focus))
                st.caption("Team: " + ", ".join(m.name for m in v.members))
            b.button("Open", key=f"open_{v.id}", type="primary", width="stretch",
                     on_click=state.open_venture, args=(v.id,))
    create_tab, join_tab = st.tabs(["Create a project", "Join a project"])
    with create_tab:
        prefix = f"create_project_{account.id}"
        if st.session_state.get(f"{prefix}_pending"):
            _choose_mentor(account, prefix)
        else:
            _create_form(account, prefix)
    with join_tab:
        _join_form(account)


# ---- create, step 1: the basics and two questions ----
def _create_form(account: access.Account, prefix: str) -> None:
    st.caption("Tell us about your venture so we can recommend the right Virtual EIR for you.")
    with st.form(prefix):
        st.text_input("Project name", key=f"{prefix}_name")
        st.text_input("One-line description", placeholder="Who do you help, and with what?",
                      key=f"{prefix}_description")
        st.radio("Has anyone outside your team signed up, tried it or paid?", list(Traction), index=1,
                 format_func=lambda t: t.value, horizontal=True, key=f"{prefix}_traction")
        st.radio("What do you need first?", list(Goal), format_func=lambda g: g.value, horizontal=True,
                 key=f"{prefix}_goal")
        with st.expander("Optional context"):
            a, b = st.columns(2)
            a.selectbox("Current situation (approximate)", list(Stage), format_func=lambda s: s.value,
                        key=f"{prefix}_stage")
            b.selectbox("Project type", list(VentureType), format_func=lambda t: t.value, key=f"{prefix}_type")
            st.caption("Background labels, not a required sequence or a progress score.")
            st.selectbox("Your background", BACKGROUNDS, index=len(BACKGROUNDS) - 1, key=f"{prefix}_background")
            st.checkbox("Involves university-owned or other sensitive IP", key=f"{prefix}_ip")
        st.form_submit_button("Next: choose your Virtual EIR", type="primary", key=f"{prefix}_submit",
                              on_click=_prepare, args=(prefix,))
    if error := st.session_state.get(f"{prefix}_error"):
        st.error(error)


def _prepare(prefix: str) -> None:
    """Keep the answers (form values) for step 2."""
    values = st.session_state
    if not values[f"{prefix}_name"].strip():
        values[f"{prefix}_error"] = "Enter a project name."
        return
    values.pop(f"{prefix}_error", None)
    fields = ("name", "description", "traction", "goal", "stage", "type", "background", "ip")
    values[f"{prefix}_pending"] = {f: values[f"{prefix}_{f}"] for f in fields}


# ---- create, step 2: the recommendation, and the team's choice ----
def _choose_mentor(account: access.Account, prefix: str) -> None:
    p = st.session_state[f"{prefix}_pending"]
    recommended = modes.recommend(p["traction"], p["goal"], p["type"])
    with st.container(border=True, key="choose_mentor"):
        st.markdown("#### Choose your Virtual EIR")
        st.markdown(f"We recommend **{modes.SHORT_NAMES[recommended]}** based on your venture’s current stage and goals.")
        for col, mode in zip(st.columns(2), LeadMode):
            with col, st.container(border=True):
                st.markdown(f"**{modes.NAMES[mode]}**" + (" · recommended" if mode == recommended else ""))
                st.caption(modes.DESCRIPTIONS[mode])
                st.button(f"Start with {modes.SHORT_NAMES[mode]}", key=f"{prefix}_start_{mode.value}",
                          type="primary" if mode == recommended else "secondary", width="stretch",
                          on_click=_create_workspace, args=(account, prefix, mode))
        st.caption("Your Virtual EIR is an AI advisor that complements AIN’s human EIRs. "
                   "You can switch later and keep your venture’s records.")
        st.button("Back", key=f"{prefix}_back", icon=":material/arrow_back:", on_click=st.session_state.pop,
                  args=(f"{prefix}_pending", None))


def _create_workspace(account: access.Account, prefix: str, mode: LeadMode) -> None:
    """Commit before the next app render chooses its route."""
    p = st.session_state.pop(f"{prefix}_pending")
    v = teams.create_workspace(state.repo(), account, p["name"], p["description"], background=p["background"],
                               stage=p["stage"], venture_type=p["type"], ip_sensitive=p["ip"], lead_mode=mode,
                               traction=p["traction"], goal=p["goal"])
    state.open_venture(v.id)


# ---- join ----
def _join_form(account: access.Account) -> None:
    code = st.text_input("Invitation code", placeholder="AIN-…", key=f"join_code_{account.id}")
    if not code.strip():
        st.caption("Ask the project owner for the demo code shown under Members in the project menu.")
        return
    v = teams.find_invited_venture(state.repo(), code)
    if v is None:
        st.warning("No project matches this code on this computer.")
        return
    with st.container(border=True):
        st.markdown(f"#### {escape(v.name)}")
        st.write(f"Invitation preview · {len(v.members)} current members · {modes.NAMES[v.lead_mode]}")
        if v.member_for_account(account.id):
            st.info("You are already a member of this project.")
            st.button("Open the joined project", key=f"open_joined_{v.id}_{account.id}",
                      on_click=state.open_venture, args=(v.id,))
            return
        st.write(f"Join as **{account.name}** (`{account.id}`). Members share the Virtual EIR chat, the Overview and the "
                 "Action Plan.")
        st.selectbox("Your background for this project", BACKGROUNDS, index=len(BACKGROUNDS) - 1,
                     key=f"join_background_{account.id}")
        st.button("Join project", type="primary", key=f"join_submit_{account.id}",
                  on_click=_accept_invitation, args=(account,))
        if error := st.session_state.get(f"join_error_{account.id}"):
            st.error(error)


def _accept_invitation(account: access.Account) -> None:
    """Join before rerender, avoiding a transient mixture of lobby and workspace."""
    v = teams.find_invited_venture(state.repo(), st.session_state.get(f"join_code_{account.id}", ""))
    if v is None:
        st.session_state[f"join_error_{account.id}"] = "This invitation is no longer available."
        return
    st.session_state.pop(f"join_error_{account.id}", None)
    teams.join_venture(v, account, st.session_state.get(f"join_background_{account.id}", "Other"))
    state.repo().save(v)
    state.open_venture(v.id)
