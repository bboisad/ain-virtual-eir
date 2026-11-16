"""The consultant rail and drawer on the Virtual EIR page (design decision 1; docs/DECISIONS.md, "Consultant drawer").

- The rail on the right shows every consultant: grey = not used yet (a click asks the lead mentor to bring them in),
  a ring = in progress, plain colour = done.
- The drawer opens leftward over most of the page, on top of the Virtual EIR chat; a strip of the chat stays visible.
  Collapsing it never ends the consultation.
- While the drawer is open the Virtual EIR's input is hidden, so a message cannot go to the wrong mentor.
- The student ends the consultation (or accepts the consultant's proposal to end), previews the fixed-format summary,
  adds one line, and sends it to the lead mentor, who answers in the Virtual EIR chat.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from eir import actions, consult
from eir.models import CONSULTANT, Consultation, ConsultationStatus, ConsultationSummary, Message
from ui import state
from ui.components import avatar, consultant_avatar, md, when

STATE_HELP = {"unused": "not used yet: click to ask your Virtual EIR to bring them in", "open": "in progress",
              "done": "done: click to see the summary"}
MAX_SUGGESTIONS = 3


# ---- the rail ----
def render_rail(ctx: state.PageContext) -> None:
    items = consult.rail(ctx.venture)
    colours = "".join(f"[class*='st-key-railitem_{i.spec.id}_'] button{{background:{i.spec.color} !important;"
                      f"color:#fff !important;border-color:{i.spec.color} !important}}" for i in items)
    st.markdown(f"<style>.block-container{{padding-right:100px}}{colours}</style>", unsafe_allow_html=True)
    with st.container(key="consult_rail"):
        st.markdown("<div class='rail-title'>AI consultants</div>", unsafe_allow_html=True)
        for item in items:
            with st.container(key=f"railitem_{item.spec.id}_{item.state}"):
                st.button(item.spec.initials, key=f"rail_{item.spec.id}", on_click=_rail_click,
                          args=(item.spec.id, item.state), help=f"{item.spec.name} AI consultant · {STATE_HELP[item.state]}")
                st.markdown(f"<div class='rail-name'>{escape(item.spec.name.split()[0])}</div>", unsafe_allow_html=True)


def _rail_click(consultant_id: str, rail_state: str) -> None:
    if rail_state == "unused":
        state.request_invite(consultant_id)
    elif state.drawer() == consultant_id:
        state.close_drawer()
    else:
        state.open_drawer(consultant_id)


def handle_invite(ctx: state.PageContext) -> None:
    """A member clicked a consultant who is not working with them: the lead mentor brings them in with a brief."""
    consultant_id = state.pop_invite()
    if not consultant_id:
        return
    v = ctx.venture
    with st.spinner(f"Your Virtual EIR is writing a brief for the {consult.name_of(consultant_id)} consultant…"):
        try:
            _, standard = actions.request_consultant(v, ctx.coach, ctx.user_id, consultant_id, files=ctx.files)
        except (ValueError, PermissionError) as err:
            state.flash("error", str(err))
            st.rerun()
    ctx.save()
    if standard:
        state.flash("info", "Your Virtual EIR did not write a brief this time, so the consultant starts from your current "
                            "focus.", "drawer")
    state.open_drawer(consultant_id)
    st.rerun()


# ---- the drawer ----
def render_drawer(ctx: state.PageContext) -> bool:
    """Show the open drawer, if any. Returns whether it is open."""
    consultant_id = state.drawer()
    history = consult.history(ctx.venture, consultant_id) if consultant_id else []
    if not history:
        state.close_drawer()
        return False
    s = consult.spec(consultant_id)
    c = ctx.venture.open_consultation(consultant_id) or history[-1]
    with st.container(key="consult_drawer"):
        _header(ctx, s, c)
        _flash()
        if c.status == ConsultationStatus.OPEN:
            _open(ctx, s, c)
        else:
            _done(ctx, s, c)
        earlier = [x for x in history if x is not c]
        if earlier:
            with st.expander(f"Earlier consultations ({len(earlier)})", icon=":material/history:"):
                for x in reversed(earlier):
                    st.markdown(f"**{md(x.question)}** <span class='muted'>· {escape(when(x.ended_at or x.started_at))}"
                                "</span>", unsafe_allow_html=True)
                    if x.summary:
                        _summary_body(x.summary)
    return True


def _header(ctx: state.PageContext, s: consult.ConsultantSpec, c: Consultation) -> None:
    """Name and status; "End and send back" (while the consultation runs) and "Collapse" stay in view."""
    running = c.status == ConsultationStatus.OPEN
    head, end, collapse = st.columns([4, 2.1, 1.3], vertical_alignment="center")
    status = "in progress" if running else f"done {when(c.ended_at)}"
    head.markdown(f"<div class='drawer-head'><img src='{consultant_avatar(s.initials, s.color)}' width='38'>"
                  f"<div><b>{escape(s.name)} AI consultant</b><br><span class='muted'>AI advisor · "
                  f"{escape(status)}</span></div></div>", unsafe_allow_html=True)
    if running and c.draft is None and end.button(
            "End and send back", key=f"end_{c.id}", icon=":material/outbox:", width="stretch",
            help="The consultant writes a summary for your Virtual EIR; you check it before it is sent"):
        _draft(ctx, c)
    collapse.button("Collapse", key="drawer_collapse", icon=":material/chevron_right:", width="stretch",
                    on_click=state.close_drawer, help="Back to your Virtual EIR. The consultation stays open.")


def _flash() -> None:
    f = state.pop_flash("drawer")
    if f:
        getattr(st, f[0])(f[1])


def _message(ctx: state.PageContext, s: consult.ConsultantSpec, m: Message) -> None:
    v = ctx.venture
    team = m.author != CONSULTANT
    member = v.member(m.author) if team else None
    with st.chat_message("user" if team else "assistant",
                         avatar=avatar(v, m.author) if team else consultant_avatar(s.initials, s.color)):
        st.caption(f"{member.name if member else s.name + ' AI consultant'} · {when(m.created_at)}")
        st.markdown(md(m.text))


def _open(ctx: state.PageContext, s: consult.ConsultantSpec, c: Consultation) -> None:
    v = ctx.venture
    with st.expander("Brief from your Virtual EIR", icon=":material/assignment:"):
        st.markdown(md(c.brief))
        st.caption("The consultant sees this brief and a read-only overview of your project, never your chat with "
                   "your Virtual EIR." + (" Technical details are withheld: IP-sensitive project." if v.ip_sensitive else ""))
    if c.draft is not None:  # the summary comes first now; the conversation folds away
        _preview(ctx, c)
        with st.expander(f"The conversation ({len(c.messages)} messages)", icon=":material/forum:"):
            for m in c.messages:
                _message(ctx, s, m)
        return
    transcript = st.container(height=440, key="consult_transcript", autoscroll=True, border=False)
    with transcript:
        for m in c.messages:
            _message(ctx, s, m)
    if consult.awaiting_reply(c) and st.button("Ask the consultant again", key=f"consult_retry_{c.id}",
                                                icon=":material/refresh:"):
        with transcript, st.spinner("The consultant is thinking…"):
            try:
                actions.consult_retry(v, ctx.coach, c.id, ctx.user_id)
            except Exception as err:  # noqa: BLE001 - keep the drawer usable and say what happened
                state.flash("error", f"The consultant could not reply: {str(err)[:200]}", "drawer")
        ctx.save()
        st.rerun()
    if c.proposed_end:
        with st.container(border=True, key="consult_proposal"):
            st.markdown(f"**The {s.name.lower()} consultant thinks your Virtual EIR's question is answered.** "
                        "Review the summary before it goes back, or keep talking.")
            a, b, _ = st.columns([1.4, 1.2, 2])
            if a.button("Review the summary", key=f"review_{c.id}", type="primary", icon=":material/summarize:"):
                _draft(ctx, c)
            if b.button("Keep talking", key=f"keep_{c.id}"):
                actions.keep_talking(v, c.id, ctx.user_id)
                ctx.save()
                st.rerun()
    picked = _suggestions(ctx, c)
    if v.ip_sensitive:
        st.caption("IP-sensitive project: discuss business questions without pasting technical details.")
    text = st.chat_input(f"Message the {s.name.lower()} AI consultant", key=f"consult_input_{c.id}")
    if text and text.strip():
        picked = text
    if picked:
        _send(ctx, s, c, picked, transcript)


def _suggestions(ctx: state.PageContext, c: Consultation) -> str:
    examples = ctx.coach.consult_suggestions(ctx.venture, c, ctx.user_id)[:MAX_SUGGESTIONS]
    if not examples:
        return ""
    picked = ""
    with st.expander("Prepared messages (demo)", icon=":material/bolt:"):
        for i, text in enumerate(examples):
            if st.button(md(text), key=f"csuggest_{c.id}_{i}", width="stretch"):
                picked = text
    return picked


def _send(ctx: state.PageContext, s: consult.ConsultantSpec, c: Consultation, text: str, transcript) -> None:
    v = ctx.venture
    with transcript:
        with st.chat_message("user", avatar=avatar(v, ctx.user_id)):
            st.markdown(md(text))
        with st.chat_message("assistant", avatar=consultant_avatar(s.initials, s.color)), \
                st.spinner("The consultant is thinking…"):
            try:
                actions.consult_message(v, ctx.coach, c.id, ctx.user_id, text)
            except Exception as err:  # noqa: BLE001 - the member's message is kept; say what happened
                state.flash("error", f"Your message was kept, but the consultant could not reply: {str(err)[:200]}",
                            "drawer")
    ctx.save()
    st.rerun()


def _draft(ctx: state.PageContext, c: Consultation) -> None:
    with st.spinner("The consultant is writing the summary…"):
        try:
            actions.draft_summary(ctx.venture, ctx.coach, c.id, ctx.user_id)
        except Exception as err:  # noqa: BLE001 - nothing was sent; the student can try again
            state.flash("error", f"The consultant could not write the summary right now: {str(err)[:200]}", "drawer")
    ctx.save()
    st.rerun()


# ---- the summary: preview, send, and the record of what was sent ----
def _summary_body(s: ConsultationSummary) -> None:
    if s.question:
        st.markdown(f"**Question:** {md(s.question)}")
    rows = (("Conclusions", s.conclusions), ("Evidence still missing", s.missing_evidence),
            ("Suggested to-dos (your Virtual EIR decides)", s.suggested_todos), ("Where you disagreed", s.disagreements),
            ("Left for your Virtual EIR (outside this consultant's scope)", s.out_of_scope))
    for title, items in rows:
        if items:
            st.markdown(f"**{title}**\n" + "\n".join(f"- {md(x)}" for x in items))
    st.markdown("**Needs a human EIR:** " + (f"yes, {md(s.human_topic)}" if s.needs_human else "no"))
    if s.student_note:
        st.markdown(f"**Your note to your Virtual EIR:** {md(s.student_note)}")


def _preview(ctx: state.PageContext, c: Consultation) -> None:
    v = ctx.venture
    with st.container(border=True, key="consult_preview"):
        st.markdown("#### Summary for your Virtual EIR")
        st.caption("Your Virtual EIR receives only this summary, never this conversation. Check it before you send it.")
        _summary_body(c.draft)
        note = st.text_input("One line for your Virtual EIR (optional)", max_chars=consult.NOTE_LIMIT,
                             key=f"consult_note_{c.id}", placeholder="e.g. I still want to try $3 first")
        a, b, _ = st.columns([1.3, 1.1, 2])
        if a.button("Send to my Virtual EIR", key=f"send_{c.id}", type="primary", icon=":material/send:"):
            with st.spinner("Your Virtual EIR is reading the summary…"):
                try:
                    actions.send_summary(v, ctx.coach, c.id, ctx.user_id, note, files=ctx.files)
                except Exception as err:  # noqa: BLE001 - say what happened; nothing is lost
                    if c.status == ConsultationStatus.OPEN:  # not sent (e.g. the note is too long)
                        state.flash("error", str(err), "drawer")
                        ctx.save()
                        st.rerun()
                    state.flash("error", f"The summary was sent, but your Virtual EIR could not reply yet: {str(err)[:200]}."
                                         " Press **Ask the Virtual EIR again**.")
            ctx.save()
            state.close_drawer()
            st.rerun()
        if b.button("Keep talking", key=f"keep_{c.id}"):
            actions.keep_talking(v, c.id, ctx.user_id)
            ctx.save()
            st.rerun()


def _done(ctx: state.PageContext, s: consult.ConsultantSpec, c: Consultation) -> None:
    v = ctx.venture
    st.caption(f"Sent to your Virtual EIR {when(c.ended_at)} by {v.display_name(c.ended_by)}. Your Virtual EIR received only "
               "this summary.")
    if c.summary:
        with st.container(border=True):
            _summary_body(c.summary)
    with st.expander(f"The conversation ({len(c.messages)} messages)", icon=":material/forum:"):
        for m in c.messages:
            _message(ctx, s, m)
    st.button("Ask my Virtual EIR for a new consultation", key=f"again_{s.id}", icon=":material/add_comment:",
              on_click=state.request_invite, args=(s.id,))
