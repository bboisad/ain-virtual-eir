"""AIN staff / EIR view: venture directory, Virtual EIR judgments to check, graduation reviews, shared briefs.

No access to workspaces: conversations, canvases and venture memory stay with the team.
"""
import streamlit as st

from eir import access, roadmap
from ui import state
from ui.components import chip, chips


def render(account: access.Account) -> None:
    st.markdown("<div class='eyebrow'>AIN Center · EIRs and staff</div>", unsafe_allow_html=True)
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    a.title("Venture directory")
    b.button("Sign out", icon=":material/logout:", use_container_width=True, on_click=state.sign_out)
    st.caption("You see each venture's roadmap module, the Virtual EIR's first judgments (to check them), "
               "graduation reviews and the Human EIR briefs a team chose to share. "
               "Conversations, canvases and venture memory stay with the team.")

    repo = state.repo()
    for entry in access.staff_directory(account, repo):
        with st.container(border=True):
            a, b = st.columns([4, 1.4], vertical_alignment="center")
            a.markdown(f"#### {entry.name}")
            tags = [chip(entry.module), chip(f"{entry.team_size} member{'' if entry.team_size == 1 else 's'}")]
            if entry.reviews_pending:
                tags.append(chip(f"{entry.reviews_pending} judgment{'s' if entry.reviews_pending > 1 else ''} to check", "warn"))
            if entry.graduation_requested:
                tags.append(chip("Graduation review requested", "warn"))
            if entry.help_requested:
                tags.append(chip("Human EIR help requested", "warn"))
            with a:
                chips(*tags)
            b.metric("Shared briefs", entry.shared_brief_count)
            v = repo.get(entry.venture_id)
            _judgments(account, v)
            _graduation(account, v)
            for brief in access.shared_briefs_for_staff(account, v):
                with st.expander(f"{brief.date} · {brief.topic}"):
                    st.markdown(brief.text)


def _judgments(account: access.Account, v) -> None:
    """Calibration: an EIR checks the Virtual EIR's first READY judgments for each venture."""
    for i, j in access.judgments_for_staff(account, v):
        d = roadmap.deliverable(j.deliverable)
        with st.expander(f"Check the Virtual EIR: \"{d.title} is complete\" · {j.date}", expanded=True):
            st.caption("The Virtual EIR judged this step complete. Do you agree? Reopening sends the step back to the team "
                       "with your note, and tells us where our standard is too loose.")
            for q in d.questions:
                a = v.answer(q.id)
                st.markdown(f"- **{q.ask}** {a.text or '—'} _({a.rung.label}; needs {q.need.label})_")
            note = st.text_area("Note for the team", key=f"jn_{v.id}_{i}",
                                placeholder="What convinced you, or what is still missing")
            a, b = st.columns(2)
            ok = a.button("Agree: step complete", type="primary", key=f"jok_{v.id}_{i}", use_container_width=True)
            reopen = b.button("Reopen the step", key=f"jre_{v.id}_{i}", use_container_width=True)
            if ok or reopen:
                try:
                    access.review_judgment(account, v, i, confirm=ok, note=note)
                except ValueError as err:
                    st.error(str(err))
                else:
                    state.repo().save(v)
                    st.rerun()


def _graduation(account: access.Account, v) -> None:
    """Graduation to NextCorps: all AIN EIRs must agree. The button records their joint decision."""
    if v.graduation != "requested":
        return
    with st.expander("Graduation review (NextCorps)", expanded=True):
        st.markdown(access.graduation_packet(account, v))
        note = st.text_area("Decision note", key=f"gn_{v.id}", placeholder="What all EIRs agreed, or what is missing")
        a, b = st.columns(2)
        ok = a.button("All EIRs agree: graduate", type="primary", key=f"gok_{v.id}", use_container_width=True)
        back = b.button("Return with feedback", key=f"gback_{v.id}", use_container_width=True)
        if ok or back:
            try:
                access.decide_graduation(account, v, approve=ok, note=note)
            except ValueError as err:
                st.error(str(err))
            else:
                state.repo().save(v)
                st.rerun()
