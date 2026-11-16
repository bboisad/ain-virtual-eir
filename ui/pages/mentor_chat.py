"""Mentor: the lead mentor's chat fills the page; the consultant rail sits on the right (ui/consult_drawer.py).

- The briefing on top says what to do now (the same data as Overview blocks 1 and 2).
- Every message gets a reply. Each record the Virtual EIR updates is listed on its reply, with Undo.
- A suggested switch of lead mentor is a button; the team decides. So is a suggested practice session.
- A consultant opens in a drawer over this page; while it is open, the Virtual EIR's input is hidden.
- A file the team chose to discuss on the Overview is read and answered here (state.request_discussion).
"""
from __future__ import annotations

from html import escape

import streamlit as st

from eir import actions, changes, consult, files, memory, modes, practice, roadmap
from eir.models import EIR, SYSTEM, ConsultationStatus, LeadMode, Message, MessageKind
from ui import consult_drawer, state
from ui.components import avatar, md, mentor_avatar, when

MAX_SUGGESTIONS = 3


def render(ctx: state.PageContext) -> None:
    v = ctx.venture
    consult_drawer.handle_invite(ctx)
    _earlier_mentors(ctx)
    _briefing(ctx)
    _handoff(ctx)
    thread = v.thread(v.lead_mode)
    if not thread:
        with st.chat_message("assistant", avatar=mentor_avatar(v.lead_mode)):
            st.caption(modes.NAMES[v.lead_mode])
            st.markdown(modes.GREETING[v.lead_mode])
    latest_offer = next((m.id for m in reversed(thread) if m.suggested_mode), "")
    for m in thread:
        _message(ctx, m, offer=m.id == latest_offer)
    _discuss_file(ctx)
    _flash()
    if actions.awaiting_reply(v):
        _retry(ctx)
    consult_drawer.render_rail(ctx)
    if consult_drawer.render_drawer(ctx):
        st.caption("The consultant panel is open. Collapse it to message your Virtual EIR.")
        return
    pending = _suggestions(ctx)
    if v.ip_sensitive:
        st.caption("IP-sensitive project: share business documents only, and discuss business questions without "
                   "technical details.")
    value = st.chat_input(f"Message your {modes.NAMES[v.lead_mode]}", key=f"mentor_input_{v.id}", accept_file=True,
                          file_type=list(files.ACCEPTED), max_upload_size=files.MAX_MB)
    text, uploads = _parts(value)
    if uploads:
        _send_file(ctx, uploads[0], text)
    elif text:
        pending = text
    if pending:
        _send(ctx, pending)


def _parts(value) -> tuple[str, list]:
    """The text and the attached files of a chat submission (tests send plain text)."""
    if not value:
        return "", []
    if isinstance(value, str):
        return value.strip(), []
    return (value.text or "").strip(), list(getattr(value, "files", None) or [])


def _briefing(ctx: state.PageContext) -> None:
    with st.container(border=True, key="mentor_briefing"):
        st.markdown("<div class='eyebrow'>Briefing</div>", unsafe_allow_html=True)
        st.markdown("  \n".join(md(line) for line in memory.briefing(ctx.venture)))


def _handoff(ctx: state.PageContext) -> None:
    v = ctx.venture
    if not v.handoff:
        return
    a, b = st.columns([4, 1.3], vertical_alignment="center")
    a.info(f"**This needs a human EIR:** {md(v.handoff)}. Suggested expertise: "
           f"{roadmap.expertise_for(v.handoff).lower()}.", icon=":material/support_agent:")
    b.button("Prepare a brief", key=f"handoff_{v.id}", icon=":material/description:", width="stretch",
             on_click=state.open_dialog, args=("human",))


def _earlier_mentors(ctx: state.PageContext) -> None:
    """After a switch, the earlier mentor's chat stays readable."""
    v = ctx.venture
    for mode in LeadMode:
        thread = v.thread(mode)
        if mode == v.lead_mode or not any(m.kind == MessageKind.CHAT for m in thread):
            continue
        with st.expander(f"Earlier conversation with the {modes.NAMES[mode]} ({len(thread)} messages)",
                         icon=":material/history:"):
            for m in thread:
                _message(ctx, m, live=False)


def _message(ctx: state.PageContext, m: Message, live: bool = True, offer: bool = False) -> None:
    v = ctx.venture
    if m.author == SYSTEM or m.kind == MessageKind.EVENT:
        st.markdown(f"<div class='chat-note'>{escape(m.text)}</div>", unsafe_allow_html=True)
        return
    mentor = m.author == EIR
    with st.chat_message("assistant" if mentor else "user", avatar=avatar(v, m.author, m.mentor)):
        member = v.member(m.author)
        name = modes.NAMES[m.mentor or LeadMode.LAUNCH] if mentor else (member.name if member else m.author)
        typed = (f" · typed by {v.display_name(m.entered_by)}" if m.entered_by and m.entered_by != m.author else "")
        st.caption(f"{name} · {when(m.created_at)}{typed}")
        st.markdown(md(m.text))
        if m.file_id:
            f = v.file(m.file_id)
            st.caption(f":material/attach_file: {f.name} · version {m.file_version}" if f
                       else ":material/attach_file: a file that was later removed")
        if mentor and live:
            _consultation(ctx, m)
            _practice(ctx, m)
            _record_updates(ctx, m)
            if offer:
                _switch_offer(ctx, m)


def _record_updates(ctx: state.PageContext, m: Message) -> None:
    """What the Virtual EIR changed in the records with this reply. Undo works per action, all or nothing."""
    v = ctx.venture
    groups = [(g, [c for c in v.changes if c.group == g]) for g in m.change_groups]
    groups = [(g, cs) for g, cs in groups if cs]
    if not groups:
        return
    with st.expander(f"Record updates ({len(groups)})", icon=":material/edit_note:"):
        for g, cs in groups:
            text, button = st.columns([5, 1.1], vertical_alignment="center")
            undone = all(c.undone_at for c in cs)
            summary = "<br>".join(md(escape(c.summary)) for c in cs)
            text.markdown(f"<s>{summary}</s>" if undone else summary, unsafe_allow_html=True)
            if undone:
                button.caption(f"Undone by {v.display_name(cs[0].undone_by)}")
                continue
            problem = changes.undo_problem(v, g)
            if button.button("Undo", key=f"undo_{g}", disabled=problem is not None, width="stretch",
                             help=str(problem) if problem else "Put the record back as it was"):
                actions.undo(v, g, ctx.user_id)
                ctx.save()
                st.rerun()
        st.caption("Your Virtual EIR updates the Overview and the Action Plan from what you tell it. It never marks a "
                   "Foundry step complete: you ask for the step check on the Overview.")


def _consultation(ctx: state.PageContext, m: Message) -> None:
    """The consultation this reply opened or reports on; the button opens its drawer."""
    c = ctx.venture.consultation(m.consultation_id) if m.consultation_id else None
    if c is None:
        return
    name = consult.name_of(c.consultant)
    running = c.status == ConsultationStatus.OPEN
    st.button(f"{name} AI consultant · {'in progress: open the panel' if running else 'done: see the summary'}",
              key=f"open_consult_{m.id}", icon=":material/forum:" if running else ":material/task_alt:",
              type="tertiary", on_click=state.open_drawer, args=(c.consultant,))


def _practice(ctx: state.PageContext, m: Message) -> None:
    """The practice feedback this reply answers (opens it), and a practice session the Virtual EIR suggests (opens the
    setup on the Practice page, pre-filled; the team decides)."""
    v = ctx.venture
    r = v.rehearsal(m.rehearsal_id) if m.rehearsal_id else None
    if r is not None:
        st.button(f"Practice feedback you sent · {practice.name_of(r.character)}: open", key=f"open_practice_{m.id}",
                  icon=":material/grading:", type="tertiary", on_click=state.open_rehearsal, args=(r.id,))
    suggestion = practice.parse_suggestion(v, m.practice_suggestion)
    if suggestion is not None:
        st.button(suggestion.label, key=f"practice_suggest_{m.id}", icon=":material/record_voice_over:",
                  on_click=state.open_practice_setup, args=(str(suggestion),),
                  help="Opens the Practice page with these settings. The session is yours: your Virtual EIR sees its "
                       "feedback only if you send it.")


def _switch_offer(ctx: state.PageContext, m: Message) -> None:
    v = ctx.venture
    to = m.suggested_mode
    if to is None or to == v.lead_mode:
        return
    a, b = st.columns([1.6, 3], vertical_alignment="center")
    if a.button(f"Switch to the {modes.NAMES[to]}", key=f"switch_{m.id}", icon=":material/swap_horiz:"):
        actions.switch_mode(v, ctx.user_id, to, "Suggested by the Virtual EIR")
        ctx.save()
        st.rerun()
    b.caption("Your team decides. Every record stays, and this conversation stays readable.")


def _flash() -> None:
    f = state.pop_flash()
    if f:
        getattr(st, f[0])(f[1])


def _retry(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.caption("Your Virtual EIR has not replied to your last message yet.")
    if st.button("Ask the Virtual EIR again", key=f"retry_{v.id}", icon=":material/refresh:"):
        with st.spinner("Your Virtual EIR is thinking…"):
            try:
                actions.retry_reply(v, ctx.coach, ctx.user_id, files=ctx.files)
            except Exception as err:  # noqa: BLE001 - keep the page usable and say what happened
                state.flash("error", _failure(err))
        ctx.save()
        st.rerun()


def _suggestions(ctx: state.PageContext) -> str:
    """Prepared messages for the fictional demo ventures, so the demo runs without typing."""
    v = ctx.venture
    examples = ctx.coach.suggestions(v, ctx.user_id)[:MAX_SUGGESTIONS]
    if not examples:
        return ""
    picked = ""
    with st.expander("Prepared messages (demo)", icon=":material/bolt:"):
        for i, text in enumerate(examples):
            if st.button(md(text), key=f"suggest_{v.id}_{i}", width="stretch"):
                picked = text
    return picked


def _send(ctx: state.PageContext, text: str) -> None:
    v = ctx.venture
    with st.chat_message("user", avatar=avatar(v, ctx.user_id)):
        st.markdown(md(text))
    with st.chat_message("assistant", avatar=mentor_avatar(v.lead_mode)), st.spinner("Your Virtual EIR is thinking…"):
        try:
            actions.mentor_message(v, ctx.coach, ctx.user_id, text, files=ctx.files)
        except Exception as err:  # noqa: BLE001 - the member's message is kept; say what happened
            state.flash("error", _failure(err))
    ctx.save()
    st.rerun()


def _send_file(ctx: state.PageContext, upload, note: str) -> None:
    """A message with an attached document: stored, read and summarized, then the Virtual EIR replies."""
    v = ctx.venture
    with st.chat_message("user", avatar=avatar(v, ctx.user_id)):
        if note:
            st.markdown(md(note))
        st.caption(f":material/attach_file: {upload.name}")
    sent = len(v.conversation)
    with st.chat_message("assistant", avatar=mentor_avatar(v.lead_mode)), \
            st.spinner(f"Your Virtual EIR is reading {upload.name}…"):
        try:
            actions.upload_file(v, ctx.coach, ctx.files, ctx.user_id, upload.name, upload.getvalue(), note)
        except Exception as err:  # noqa: BLE001 - say what happened; nothing the member wrote is lost
            if len(v.conversation) > sent:  # the file and the message are saved; only the reply failed
                state.flash("error", _failure(err))
            else:  # not stored: wrong type, too large, or the same file again
                state.flash("error", f"{upload.name} was not shared: {err}")
    ctx.save()
    st.rerun()


def _discuss_file(ctx: state.PageContext) -> None:
    """A file the team chose to discuss on the Overview: its latest version goes to the Virtual EIR, which replies."""
    file_id, note = state.pop_discussion()
    if not file_id:
        return
    v = ctx.venture
    f = v.file(file_id)
    name = f.name if f else "The file"
    with st.chat_message("user", avatar=avatar(v, ctx.user_id)):
        if note:
            st.markdown(md(note))
        st.caption(f":material/attach_file: {name}")
    sent = len(v.conversation)
    with st.chat_message("assistant", avatar=mentor_avatar(v.lead_mode)), \
            st.spinner(f"Your Virtual EIR is reading {name}…"):
        try:
            actions.discuss_file(v, ctx.coach, ctx.files, ctx.user_id, file_id, note)
        except Exception as err:  # noqa: BLE001 - say what happened; the file and the message are kept
            if len(v.conversation) > sent:  # the message with the file is in the chat; only the reply failed
                state.flash("error", _failure(err))
            else:  # e.g. the file was removed meanwhile
                state.flash("error", f"{name} could not be shared: {err}")
    ctx.save()
    st.rerun()


def _failure(err: Exception) -> str:
    detail = str(err).strip()[:200]
    return ("Your message was kept, but the Virtual EIR could not reply" + (f": {detail}" if detail else ".")
            + " Check the connection, then press **Ask the Virtual EIR again**.")
