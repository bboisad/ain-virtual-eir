"""The ⋯ menu of a workspace and its dialogs: members, a human EIR, switching the lead mentor, project settings, the
preliminary project plan and stepping back a module (Launch), prototype info. One dialog is open at a time
(state.dialog()); app.py calls `render_dialog` on every run. The Overview opens its own dialogs (names "ov_…")."""
from __future__ import annotations

from datetime import date

import streamlit as st

from eir import actions, brief, modes, overview, roadmap, teams
from eir.models import LeadMode, Module, Stage, VentureType
from ui import state
from ui.components import member_row

EXPERIENCE = ("First venture", "Ran a small business or side project", "Founded a startup before")


def render_menu(ctx: state.PageContext) -> None:
    v = ctx.venture
    key = f"menu_{v.id}"
    with st.popover("Menu", icon=":material/more_horiz:", width="stretch", key=key, on_change="rerun"):
        st.caption(f"Signed in as **{ctx.account.name}**")
        items = [("members", "Members", ":material/group:"),
                 ("human", "Ask a human EIR", ":material/support_agent:"),
                 ("switch", "Switch Virtual EIR", ":material/swap_horiz:"),
                 ("settings", "Project settings", ":material/settings:")]
        if v.lead_mode == LeadMode.LAUNCH:
            items.append(("plan", "Project plan", ":material/description:"))
            prev = roadmap.previous_module(v.module)
            if prev is not None and v.module != Module.ALUMNI:
                items.append(("back", f"Step back to {roadmap.info(prev).name}", ":material/undo:"))
        for name, label, icon in items:
            st.button(label, icon=icon, key=f"menu_{name}", width="stretch", on_click=_open, args=(key, name))
        st.divider()
        st.button("My projects", icon=":material/arrow_back:", key="menu_projects", width="stretch",
                  on_click=state.leave_venture)
        st.button("Sign out", icon=":material/logout:", key="menu_signout", width="stretch", on_click=state.sign_out)
        st.button("Prototype info", icon=":material/info:", key="menu_info", width="stretch",
                  on_click=_open, args=(key, "info"))


def _open(menu_key: str, dialog: str) -> None:
    """Close the menu, then open the dialog (otherwise the menu stays on top of it)."""
    st.session_state[menu_key] = False
    state.open_dialog(dialog)


def render_dialog(ctx: state.PageContext) -> None:
    show = DIALOGS.get(state.dialog())
    if show is not None:
        show(ctx)


def _flash() -> None:
    f = state.pop_flash("dialog")
    if f:
        getattr(st, f[0])(f[1])


# ---- members ----
@st.dialog("Members", width="medium", on_dismiss=state.close_dialog)
def _members(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.caption("Each teammate joins with their own account. Messages and changes keep the contributor's identity.")
    owner = v.members[0] if v.members else None
    for member in v.members:
        with st.container(border=True):
            member_row(v, member.id, size=36)
            labels = [f"Account ID: {member.account or 'demo account'}"]
            if owner and member.id == owner.id:
                labels.append("Project owner")
            if member.id == ctx.user_id:
                labels.append("You")
            st.caption(" · ".join(labels))
            if member.id == ctx.user_id:
                options = list(EXPERIENCE)
                if member.experience and member.experience not in options:
                    options.append(member.experience)
                exp = st.selectbox("Your venture experience (the Virtual EIR adjusts how much it explains)", options,
                                   index=options.index(member.experience) if member.experience in options else 0,
                                   key=f"exp_{v.id}_{member.id}")
                if exp != member.experience:
                    actions.set_experience(v, member.id, exp, ctx.user_id)
                    ctx.save()
            elif member.experience:
                st.caption(f"Experience: {member.experience}")
    if owner and ctx.user_id == owner.id:
        st.markdown("**Invite a teammate**")
        st.write("Share this demo code; the teammate chooses **Join a project** under My projects.")
        st.code(teams.invitation_code(v), language=None)
        st.caption("The teammate previews the project and chooses to join. Entering a name does not add a member.")
    elif owner:
        st.info(f"Ask {owner.name}, the project owner, for an invitation code to invite another teammate.")


# ---- a human AIN EIR: the next Foundry session and a consent-based brief ----
@st.dialog("Ask a human EIR", width="large", on_dismiss=state.close_dialog)
def _human(ctx: state.PageContext) -> None:
    v = ctx.venture
    _flash()
    if v.handoff:
        st.info(f"Your Virtual EIR suggested a human EIR for: **{v.handoff}**. Ask AIN for an EIR with "
                f"{roadmap.expertise_for(v.handoff).lower()} experience.", icon=":material/support_agent:")
    a, b = st.columns([2, 1], vertical_alignment="bottom")
    a.markdown("**Next human EIR session**  \n<span class='muted'>The Virtual EIR works between the AIN Foundry "
               "sessions; bring the brief below.</span>", unsafe_allow_html=True)
    day = date.fromisoformat(v.next_eir_session) if v.next_eir_session else None
    picked = b.date_input("Session date", value=day, key=f"eir_session_{v.id}", format="YYYY-MM-DD")
    if (picked.isoformat() if picked else "") != v.next_eir_session:
        actions.schedule_eir_session(v, picked.isoformat() if picked else "", ctx.user_id)
        ctx.save()

    topic = st.selectbox("Help needed", brief.topics(v), key=f"brief_topic_{v.id}")
    text = st.text_area("Brief · edit before sharing", brief.mentor_brief(v, topic), height=340,
                        key=f"mentor_draft_{v.id}_{topic}")
    st.caption("Built from your records, never from your chats. AIN staff can read it only after you share it.")
    consent = st.checkbox(f"I ({v.member(ctx.user_id).name}) am authorized to share this brief with AIN staff",
                          key=f"brief_consent_{v.id}")
    left, right = st.columns(2)
    if left.button("Share with AIN", disabled=not consent, type="primary", width="stretch", key=f"share_{v.id}"):
        actions.share_brief(v, topic, text, ctx.user_id)
        ctx.save()
        state.flash("success", "Shared. AIN staff can now read this brief, and nothing else from your workspace.",
                    "dialog")
        st.rerun()
    right.download_button("Download .md", text, file_name=f"human_eir_brief_{v.id}.md", width="stretch",
                          key=f"brief_download_{v.id}")
    for shared in reversed(v.shared_briefs):
        st.caption(f"Shared {shared.date} · {shared.topic} · approved by {v.display_name(shared.approved_by)}")
    with st.expander(f"AIN resources for {roadmap.info(v.module).name}"):
        for r in roadmap.resources(v, limit=6):
            st.markdown(f"- {r.name} <span class='muted'>· {r.kind} · {r.when}</span>", unsafe_allow_html=True)


# ---- switch the lead mentor ----
@st.dialog("Switch Virtual EIR", width="medium", on_dismiss=state.close_dialog)
def _switch(ctx: state.PageContext) -> None:
    v = ctx.venture
    to = LeadMode.OPTIMIZE if v.lead_mode == LeadMode.LAUNCH else LeadMode.LAUNCH
    st.markdown(f"You are working with the **{modes.NAMES[v.lead_mode]}**.")
    st.caption(modes.DESCRIPTIONS[v.lead_mode])
    with st.container(border=True):
        st.markdown(f"**{modes.NAMES[to]}**")
        st.caption(modes.DESCRIPTIONS[to])
    if to == LeadMode.OPTIMIZE:
        ok, best = modes.entry_check(v)
        if not ok:
            st.warning("The Optimize Virtual EIR first checks what customers actually did. The strongest customer behavior "
                       f"recorded so far is {best.label.lower() if best else 'none'}; it will likely suggest staying "
                       "with the Launch Virtual EIR until someone signs up, tries or pays.")
    reason = st.text_input("Why are you switching? (optional)", key=f"switch_reason_{v.id}")
    st.caption("Every record stays. The earlier conversation stays readable on the Virtual EIR page.")
    if st.button(f"Switch to the {modes.NAMES[to]}", type="primary", key=f"switch_to_{v.id}"):
        actions.switch_mode(v, ctx.user_id, to, reason)
        ctx.save()
        state.go_to("Mentor")
        st.rerun()


# ---- project settings ----
@st.dialog("Project settings", width="medium", on_dismiss=state.close_dialog)
def _settings(ctx: state.PageContext) -> None:
    v = ctx.venture
    with st.form(f"settings_{v.id}", border=False):
        name = st.text_input("Project name", v.name)
        description = st.text_area("One-line description", v.description, height=80)
        a, b = st.columns(2)
        stage = a.selectbox("Current situation (approximate)", list(Stage), index=list(Stage).index(v.stage),
                            format_func=lambda s: s.value)
        kind = b.selectbox("Project type", list(VentureType), index=list(VentureType).index(v.type),
                           format_func=lambda t: t.value)
        ip = st.checkbox("Involves university-owned or other sensitive IP", value=v.ip_sensitive,
                         help="Your Virtual EIR and consultants then never ask for technical details.")
        saved = st.form_submit_button("Save settings", type="primary")
    if saved:
        try:
            teams.save_project_details(v, ctx.user_id, name, description, stage, kind, ip)
        except ValueError as err:
            st.error(str(err))
            return
        ctx.save()
        state.close_dialog()
        st.rerun()


# ---- the Launch Virtual EIR's exit artifact, and stepping back a module (moved here from the Overview in v0.19) ----
@st.dialog("Project plan", width="medium", on_dismiss=state.close_dialog)
def _plan(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.markdown("A one-page preliminary project plan, built from your records: the problem, your first customer, the "
                "canvas with its evidence, the riskiest assumptions and the next 30 days.")
    st.download_button("Download the plan (.md)", overview.preliminary_plan(v), file_name=f"project_plan_{v.id}.md",
                       key=f"plan_{v.id}", icon=":material/download:", type="primary")


@st.dialog("Step back a module", width="medium", on_dismiss=state.close_dialog)
def _back(ctx: state.PageContext) -> None:
    v = ctx.venture
    prev = roadmap.previous_module(v.module)
    if prev is None or v.module == Module.ALUMNI:
        st.caption("There is no earlier module to go back to.")
        return
    st.markdown(f"Go back to **{roadmap.info(prev).name}**.")
    st.caption("If a core assumption was refuted (for example nobody will pay), going back is progress. Your Virtual "
               "EIR sees the reason in the project history.")
    reason = st.text_input("What changed?", key=f"rm_back_reason_{v.id}",
                           placeholder="Fee test: 0 of 10 students paid $3")
    if st.button("Step back", key=f"rm_back_{v.id}", type="primary"):
        try:
            actions.step_back(v, ctx.user_id, reason)
        except ValueError as err:
            st.error(str(err))
            return
        ctx.save()
        state.close_dialog()
        st.rerun()


# ---- prototype info ----
@st.dialog("Prototype info", on_dismiss=state.close_dialog)
def _info(ctx: state.PageContext) -> None:
    st.markdown(f"**Virtual EIR model:** {ctx.coach.label}")
    st.caption("Demo data is fictional and saved on this computer, so it survives a refresh. Reset puts the demo "
               "ventures back as they were.")
    st.button("Reset demo", key="reset_demo", on_click=state.reset)


DIALOGS = {"members": _members, "human": _human, "switch": _switch, "settings": _settings, "plan": _plan,
           "back": _back, "info": _info}
