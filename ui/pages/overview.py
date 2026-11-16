"""Overview: the project's homepage (v0.19, designed from two rounds of outside feedback; docs/DECISIONS.md).

It answers three questions: what are we doing, where are we stuck, what do we do next.
- header: the project in the team's words (Team statement · Edit);
- the focus card, the page's main block: the current focus (the Virtual EIR's suggestion), why now, the evidence
  for and against (each with its level and where it comes from), what is missing, the next step and one main button;
- progress: the four Foundry deliverables and the key question to answer now;
- snapshot: customer, solution and business model in the team's words, next to the graded records, or the Virtual
  EIR's draft from the canvas, which the team can adopt;
- recent activity and files, side by side.

Everything else opens in a dialog from where it belongs: the key questions from the progress, the canvas from the
snapshot, the history from the activity, all files from the files. A project nobody has worked on yet gets a start
page instead. The assumptions live in the Action Plan. The data comes from eir/overview.py and eir/files.py.
"""
from __future__ import annotations

import zlib
from html import escape
from pathlib import PurePath

import streamlit as st

from eir import actions, files, modes, overview, questioning, roadmap, teams
from eir.models import EIR, Experiment, FileKind, LeadMode, Module, ReviewState, Verdict
from ui import state
from ui.components import chip, chips, evidence_popover, md, source_tag, when

PREVIEW_CHARS = 1500
SHORT = 120  # characters of the team's text on a snapshot line
RECENT = 3  # changes and files shown on the page; the dialogs show all
NEXT_FIELD = {"customer": "solution", "solution": "revenue"}  # completing the snapshot goes on to the next line
PLACEHOLDER = {"customer": "Who exactly, and how many of them?", "solution": "What you offer them, in one line",
               "revenue": "Who pays, how much, for what"}
CTA = {"start": ("Review and start the test", "Action Plan", ":material/science:"),
       "result": ("Record the result", "Action Plan", ":material/edit_note:"),
       "task": ("Open the Action Plan", "Action Plan", ":material/checklist:"),
       "chat": ("Ask your Virtual EIR what to test", state.HOME, ":material/forum:")}


def render(ctx: state.PageContext) -> None:
    v = ctx.venture
    _header(ctx)
    _flash()
    if overview.is_new(v):
        _start_page(ctx)
    else:
        _focus_card(ctx)
        _progress(ctx)
        _snapshot(ctx)
        _activity_and_files(ctx)
        st.button("Need a human EIR? Ask for a review", type="tertiary", key=f"ov_human_{v.id}",
                  icon=":material/support_agent:", on_click=state.open_dialog, args=("human",))
    _dialogs(ctx)


def _flash(where: str = "page") -> None:
    f = state.pop_flash(where)
    if f:
        getattr(st, f[0])(f[1])


def _short(text: str, limit: int = SHORT) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _key(name: str, saved: str) -> str:
    """The key of a box that edits saved text. It changes when that text is saved, here or elsewhere (e.g. the
    settings dialog renames the project), so the box shows the saved text again: a box with a fixed key keeps what
    it showed."""
    return f"{name}_{zlib.crc32(saved.encode('utf-8')):08x}"


def _who(v, by: str) -> str:
    if by == EIR:
        return "your Virtual EIR"
    return v.display_name(by) if v.member(by) else {"team": "your team", "AIN": "AIN"}.get(by, by)


# ---- header: the project in the team's words ----
def _header(ctx: state.PageContext) -> None:
    v, p = ctx.venture, ctx.venture.profile
    with st.container(key="ov_head"):
        title, side = st.columns([3, 1.6], vertical_alignment="bottom")
        title.markdown(f"## {escape(v.name)}")
        who = v.display_name(p.completed_by) if p.completed_by and v.member(p.completed_by) else ""
        meta = f"{who} · {p.completed_on}" if who and p.completed_on else "not confirmed yet"
        with side, st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            st.markdown(f"{source_tag('team')} <span class='muted'>{md(escape(meta))}</span>", unsafe_allow_html=True)
            st.button("Edit" if who else "Confirm", type="tertiary", key=f"ov_edit_intro_{v.id}", icon=":material/edit:",
                      on_click=state.open_dialog, args=("ov_intro",))
        st.markdown(f"<div class='ov-line'>{escape(v.description)}</div>" if v.description else
                    "<div class='muted'>Add one line: who you help, and with what.</div>", unsafe_allow_html=True)
        if p.problem:
            st.markdown(f"<div class='muted'>Problem: {escape(_short(p.problem, 170))}</div>", unsafe_allow_html=True)


# ---- a new project: a start page, not an empty dashboard ----
def _start_page(ctx: state.PageContext) -> None:
    v = ctx.venture
    with st.container(key="ov_start"):
        st.markdown(f"{source_tag('eir')} <span class='eyebrow'>Your Virtual EIR · {modes.SHORT_NAMES[v.lead_mode]}"
                    "</span>", unsafe_allow_html=True)
        st.markdown("### Your project, just started.")
        st.markdown("You don't need a business plan yet. Start by telling your Virtual EIR who might need this, and "
                    "why you think so.")
        st.button("Start the conversation", type="primary", key=f"ov_start_chat_{v.id}", icon=":material/forum:",
                  on_click=state.go_to, args=(state.HOME,))
        with st.container(horizontal=True, gap="small", vertical_alignment="center"):
            st.markdown("<span class='muted'>Already have material?</span>", unsafe_allow_html=True)
            st.button("Upload a file", type="tertiary", key=f"ov_start_upload_{v.id}", icon=":material/upload:",
                      on_click=state.open_dialog, args=("ov_add_file",))
            st.button("Invite your team", type="tertiary", key=f"ov_start_invite_{v.id}", icon=":material/group:",
                      on_click=state.open_dialog, args=("members",))
    st.caption("Your page fills in as you talk: the customer, the problem, your assumptions and the evidence for them.")


# ---- the focus card: the page's main block ----
def _line(label: str, text: str, rung=None, sources=(), key: str = "") -> None:
    a, b, c = st.columns([1.15, 4.2, 2], vertical_alignment="center")
    a.markdown(f"<span class='ov-k'>{escape(label)}</span>", unsafe_allow_html=True)
    b.markdown(md(escape(text)) if text else "<span class='muted'>Nothing recorded yet</span>", unsafe_allow_html=True)
    if rung is not None:
        with c:
            evidence_popover(rung, sources, key=key)


def _focus_card(ctx: state.PageContext) -> None:
    v = ctx.venture
    c = overview.focus_card(v)
    with st.container(key="ov_focus"):
        st.markdown(f"{source_tag('eir')} <span class='eyebrow'>Current focus</span>", unsafe_allow_html=True)
        st.markdown(f"### {md(escape(c.question))}")
        if c.owner not in ("your Virtual EIR", "the key questions"):
            st.caption(f"Set by {c.owner}")
        if c.why:
            _line("Why now", c.why)
        _line("Evidence for", c.known.text if c.known else "", c.known.rung if c.known else None, c.sources,
              f"ev_for_{v.id}")
        if c.against is not None:
            _line("Evidence against", c.against.text, c.against.rung, c.sources, f"ev_against_{v.id}")
        if c.missing:
            _line("Still missing", c.missing)
        if c.next is not None:
            who = overview.set_by(v, c.next.created_by)
            _line("Next step", _next_line(v, c.next) + (f" Planned by {who}." if who and who != "your Virtual EIR"
                                                        else ""))
        if v.handoff:
            st.info(f"Your Virtual EIR suggests a human EIR for: {md(v.handoff)}", icon=":material/support_agent:")
        label, page, icon = CTA[c.cta]
        other = ("Ask your Virtual EIR", state.HOME) if page != state.HOME else ("Open the Action Plan", "Action Plan")
        with st.container(horizontal=True, gap="small"):
            st.button(label, type="primary", key=f"ov_cta_{v.id}", icon=icon, on_click=state.go_to, args=(page,))
            st.button(other[0], key=f"ov_cta2_{v.id}", on_click=state.go_to, args=(other[1],))
        st.caption("A suggestion: your team decides.")


# ---- progress: the deliverables, in words ----
def _progress(ctx: state.PageContext) -> None:
    v = ctx.venture
    with st.container(key="ov_progress"):
        if v.lead_mode == LeadMode.OPTIMIZE:
            s = overview.status(v)
            st.markdown(f"**{md(escape(s.position))}** · {md(escape(s.progress))}")
            _optimize_state(ctx)
            st.button("See the six lenses", type="tertiary", key=f"ov_lenses_{v.id}", icon=":material/grid_view:",
                      on_click=state.open_dialog, args=("ov_canvas",))
            return
        if v.module == Module.ALUMNI:
            st.success("All AIN EIRs agreed: this venture graduated to NextCorps.")
            return
        pills = " ".join(f"<span class='ov-step {s.state}'>{'✓ ' if s.state == 'done' else ''}{escape(s.title)}</span>"
                         for s in overview.steps(v))
        st.markdown(f"<div class='ov-steps'>{pills}</div>", unsafe_allow_html=True)
        d, q = roadmap.current_deliverable(v), overview.current_question(v)
        if d is None:
            st.markdown("Every deliverable of this module is done.")
        else:
            p = roadmap.progress(v, d)
            counted = f"{p.answered} of {p.total} key questions have enough evidence"
            if q is not None and q.ask == overview.status(v).focus:  # the focus card already asks it
                st.markdown(f"<span class='muted'>{counted}</span>", unsafe_allow_html=True)
            else:
                now = f"Now: {q.ask}" if q else f"Every key question of the {d.short.lower()} has enough evidence."
                st.markdown(f"{md(escape(now))}  \n<span class='muted'>{counted}</span>", unsafe_allow_html=True)
        latest = v.judgments[-1] if v.judgments else None
        if latest is not None and latest.review == ReviewState.PENDING:
            chips(chip("An AIN EIR will check your last step check", "warn"))
        st.button("See all key questions" if d else "Graduation review", type="tertiary", key=f"ov_questions_{v.id}",
                  icon=":material/quiz:", on_click=state.open_dialog, args=("ov_questions",))


def _optimize_state(ctx: state.PageContext) -> None:
    v = ctx.venture
    if modes.optimize_complete(v):
        st.success("Bottleneck found and one experiment on it has a conclusion: this round of optimizing is done.")
    elif v.diagnosis.bottleneck:
        if v.diagnosis.why:
            st.caption(f"Why: {md(v.diagnosis.why)}")
    else:
        st.caption("Your Virtual EIR grades the six lenses with you, then names the bottleneck.")


# ---- snapshot: the team's words next to the graded records ----
def _snapshot(ctx: state.PageContext) -> None:
    v = ctx.venture
    items = overview.essentials(v)
    head, link = st.columns([3, 1.6], vertical_alignment="bottom")
    head.markdown(f"#### Snapshot {source_tag('team')}", unsafe_allow_html=True)
    with link, st.container(horizontal=True, horizontal_alignment="right"):
        st.button("See the full canvas" if v.lead_mode == LeadMode.LAUNCH else "See the six lenses", type="tertiary",
                  key=f"ov_canvas_{v.id}", icon=":material/grid_view:", on_click=state.open_dialog,
                  args=("ov_canvas",))
    if not any(i.text or i.record_text for i in items):
        with st.container(border=True, key="ov_snapshot_todo"):
            st.markdown("**Complete your project snapshot**  \nWho you serve, what you offer and how you make money, "
                        "in a line each.")
            st.button("Complete it", key=f"ov_snapshot_start_{v.id}", icon=":material/edit:",
                      on_click=state.open_dialog, args=("ov_core:customer",))
        return
    with st.container(key="ov_snapshot"):
        for item in items:
            a, b, c = st.columns([1.3, 4.4, 2], vertical_alignment="center")
            a.button(item.title, type="tertiary", key=f"ov_core_{v.id}_{item.field}", icon=":material/edit_note:",
                     help="View and edit", on_click=state.open_dialog, args=(f"ov_core:{item.field}",))
            if item.text:
                b.markdown(md(escape(_short(item.text))))
            elif item.record_text:
                b.markdown(f"<span class='ov-draft'>✦ Drafted by your Virtual EIR:</span> "
                           f"{md(escape(_short(item.record_text)))}", unsafe_allow_html=True)
            else:
                b.markdown("<span class='muted'>Not written yet</span>", unsafe_allow_html=True)
            with c:
                if item.rung:
                    evidence_popover(item.rung, (overview.Source(item.record_text, item.rung, item.source),),
                                     key=f"ev_core_{v.id}_{item.field}")
                else:
                    st.markdown("<span class='muted'>Not graded yet</span>", unsafe_allow_html=True)


# ---- recent activity and files ----
def _activity_and_files(ctx: state.PageContext) -> None:
    v = ctx.venture
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(f"#### Recent activity {source_tag('records')}", unsafe_allow_html=True)
        items = overview.recent_changes(v, limit=RECENT, events=True)
        if not items:
            st.caption("Nothing yet. What your Virtual EIR records from your conversations appears here.")
        for r in items:
            st.markdown(f"{md(escape(r.text))}  \n<span class='muted'>{escape(_who(v, r.by))} · "
                        f"{escape(when(r.when))}</span>", unsafe_allow_html=True)
        st.button("View full history", type="tertiary", key=f"ov_history_{v.id}", icon=":material/history:",
                  on_click=state.open_dialog, args=("ov_history",))
    with right:
        _files_summary(ctx)


def _ordered_files(v) -> list:
    return sorted((f for f in v.files if f.latest is not None), key=lambda f: f.latest.at, reverse=True)


def _status_word(v, f) -> str:
    if f.kind == FileKind.LINK:
        return "link"
    if files.discussion(v, f):
        return "discussed"
    return "read by your Virtual EIR" if files.read_by_eir(f, f.latest) else "not discussed yet"


def _files_summary(ctx: state.PageContext) -> None:
    v = ctx.venture
    ordered = _ordered_files(v)
    st.markdown("#### Files")
    if ordered:
        st.caption(f"{len(ordered)} file{'s' if len(ordered) != 1 else ''} · updated {when(ordered[0].latest.at)}")
    else:
        st.caption("No files yet: your plan, pitch deck, interview notes or research.")
    if state.dialog() != "ov_add_file":  # the dialog shows the same offer
        _saved_offer(ctx)
    for f in ordered[:RECENT]:
        a, b = st.columns([3, 2], vertical_alignment="center")
        a.button(_short(f.name, 40), type="tertiary", key=f"ov_file_{f.id}", icon=":material/description:",
                 on_click=state.open_dialog, args=(f"ov_file:{f.id}",))
        b.markdown(f"<span class='muted'>{escape(when(f.latest.at))} · {escape(_status_word(v, f))}</span>",
                   unsafe_allow_html=True)
    with st.container(horizontal=True, gap="small"):
        st.button("Add a file", key=f"ov_add_{v.id}", icon=":material/add:", on_click=state.open_dialog,
                  args=("ov_add_file",))
        if ordered:
            st.button(f"All files ({len(ordered)})", type="tertiary", key=f"ov_all_files_{v.id}",
                      on_click=state.open_dialog, args=("ov_files",))


def _saved_offer(ctx: state.PageContext) -> None:
    """The file just saved: shall the Virtual EIR read and discuss it? (Saved files are never read until asked.)"""
    v = ctx.venture
    f = v.file(state.saved_file()) if state.saved_file() else None
    if f is None or f.latest is None or files.discussion(v, f) is not None:
        return  # removed, or already discussed (e.g. from the chat)
    with st.container(border=True, key="ov_saved"):
        st.markdown(f"**Saved {md(escape(f.name))}** (version {f.latest.number}). Shall your Virtual EIR read it and "
                    "discuss it with you?")
        note = st.text_input("What should your Virtual EIR look at? (optional)", key=f"ov_note_{f.id}",
                             placeholder="e.g. Is the pricing slide convincing?")
        with st.container(horizontal=True, gap="small"):
            discuss = st.button("Read and discuss it", key=f"ov_discuss_new_{f.id}", type="primary",
                                icon=":material/forum:", help="Opens the chat, where your Virtual EIR reads the file "
                                                              "and replies")
            later = st.button("Not now", key=f"ov_notnow_{f.id}")
    if discuss:
        _discuss(f.id, note)
    if later:
        state.clear_saved_file()
        state.close_dialog()
        st.rerun()


def _discuss(file_id: str, note: str = "") -> None:
    """Open the chat, where the Virtual EIR reads the file's latest version and replies (mentor_chat.py). Handled in
    the run, not in on_click: inside a dialog a click reruns only the dialog, so the page must be redrawn here. The top
    navigation follows because go_to gives it a new key."""
    state.request_discussion(file_id, note)
    st.rerun()


def _next_line(v, item) -> str:
    """The next step in a line: what to do and by when (the criteria are in the Action Plan)."""
    if isinstance(item, Experiment):
        return item.method.rstrip(".") + (f", by {item.deadline}" if item.deadline else "") + "."
    who = "the team" if item.owner == "team" else v.display_name(item.owner)
    return f"{item.text.rstrip('.')} ({who}" + (f", by {item.due_date})." if item.due_date else ").")


# ---- dialogs: what used to crowd the page, opened from where it belongs ----
def _dialogs(ctx: state.PageContext) -> None:
    name = state.dialog()
    if not name.startswith("ov_"):
        return  # the menu's dialogs are shown by ui/menu.py
    kind, _, arg = name.partition(":")
    show = {"ov_intro": _intro_dialog, "ov_core": _core_dialog, "ov_canvas": _canvas_dialog,
            "ov_questions": _questions_dialog, "ov_history": _history_dialog, "ov_add_file": _add_file_dialog,
            "ov_files": _files_dialog, "ov_file": _file_dialog}.get(kind)
    if show is None:
        state.close_dialog()
        return
    show(ctx, arg)


def _done(ctx: state.PageContext, then: str = "") -> None:
    """After a save in a dialog: store it, open the next dialog (or none), and redraw the whole page."""
    ctx.save()
    if then:
        state.open_dialog(then)
    else:
        state.close_dialog()
    st.rerun()


@st.dialog("Your project", width="medium", on_dismiss=state.close_dialog)
def _intro_dialog(ctx: state.PageContext, _: str = "") -> None:
    v, p = ctx.venture, ctx.venture.profile
    st.markdown(source_tag("team"), unsafe_allow_html=True)
    with st.form(f"intro_{v.id}", border=False):
        name = st.text_input("Project name", v.name, key=_key(f"intro_name_{v.id}", v.name))
        line = st.text_input("One line: who you help, and with what", v.description,
                             key=_key(f"intro_line_{v.id}", v.description))
        problem = st.text_area("The problem it solves", p.problem, height=90,
                               key=_key(f"intro_problem_{v.id}", p.problem))
        saved = st.form_submit_button("Save and confirm", type="primary", key=f"intro_save_{v.id}")
    st.caption("Saving confirms the description in your team's words.")
    if saved:
        try:
            teams.save_project_intro(v, ctx.user_id, name=name, one_liner=line, customer=p.customer, problem=problem)
        except (ValueError, PermissionError) as err:
            st.error(str(err))
            return
        _done(ctx)


@st.dialog("Your project snapshot", width="medium", on_dismiss=state.close_dialog)
def _core_dialog(ctx: state.PageContext, field: str = "") -> None:
    v = ctx.venture
    item = next((i for i in overview.essentials(v) if i.field == field), None)
    if item is None:
        st.caption("Nothing to edit here.")
        return
    nxt = NEXT_FIELD.get(field, "")
    then = f"ov_core:{nxt}" if nxt and not getattr(v.profile, nxt) else ""
    st.markdown(f"#### {escape(item.title)} {source_tag('team')}", unsafe_allow_html=True)
    with st.form(f"core_{v.id}_{field}", border=False):
        text = st.text_area(item.title, item.text, height=110, key=_key(f"core_text_{v.id}_{field}", item.text),
                            label_visibility="collapsed", placeholder=PLACEHOLDER.get(field, ""))
        saved = st.form_submit_button("Save" + (" and go on" if then else ""), type="primary",
                                      key=f"core_save_{v.id}_{field}")
    if saved:
        try:
            teams.save_project_essentials(v, ctx.user_id, **{field: text})
        except (ValueError, PermissionError) as err:
            st.error(str(err))
            return
        _done(ctx, then)
    if item.record_text and not item.text:
        st.markdown(f"<span class='ov-draft'>✦ Drafted by your Virtual EIR</span> from your conversations:  \n"
                    f"{md(escape(item.record_text))}", unsafe_allow_html=True)
        if st.button("Use this as our statement", key=f"ov_adopt_{v.id}_{field}", icon=":material/check:"):
            teams.save_project_essentials(v, ctx.user_id, **{field: item.record_text})
            _done(ctx, then)
    st.divider()
    st.markdown(f"**What your records show** · {escape(item.record_name)}", unsafe_allow_html=True)
    st.markdown(md(escape(item.record_text)) if item.record_text else "<span class='muted'>Nothing recorded yet</span>",
                unsafe_allow_html=True)
    if item.rung:
        evidence_popover(item.rung, (overview.Source(item.record_text, item.rung, item.source),),
                         key=f"ev_dialog_{v.id}_{field}")
    if item.why:
        st.caption(f"Why this level: {md(item.why)}")
    st.caption("Your words never change the evidence level: your Virtual EIR grades the evidence behind them.")


@st.dialog("Evidence map", width="large", on_dismiss=state.close_dialog)
def _canvas_dialog(ctx: state.PageContext, _: str = "") -> None:
    v = ctx.venture
    launch = v.lead_mode == LeadMode.LAUNCH
    st.markdown("#### Business model canvas" if launch else "#### The six lenses")
    if launch:
        st.caption("Write each block in your own words; your Virtual EIR grades the evidence behind it.")
    entries = overview.evidence_map(v)
    for row in range(0, len(entries), 3):
        for col, (i, e) in zip(st.columns(3), list(enumerate(entries))[row:row + 3]):
            with col, st.container(border=True):
                st.markdown(f"**{escape(e.name)}**")
                if e.rung:
                    evidence_popover(e.rung, (overview.Source(e.text, e.rung),), key=f"ev_map_{v.id}_{i}")
                else:
                    st.caption("Empty" if launch else "Not graded")
                if launch:
                    _canvas_block(ctx, i, e)
                else:
                    st.markdown(md(e.text) if e.text else "<span class='muted'>Not graded yet</span>",
                                unsafe_allow_html=True)
                if e.why:
                    st.caption(md(e.why))


def _canvas_block(ctx: state.PageContext, i: int, e: overview.MapEntry) -> None:
    v = ctx.venture
    text = st.text_area(e.name, e.text, height=90, key=_key(f"canvas_{v.id}_{i}", e.text), label_visibility="collapsed",
                        placeholder="Who, what, how many: in your own words")
    if text.strip() != e.text and st.button("Save", key=f"canvas_save_{v.id}_{i}"):
        try:
            actions.edit_canvas_text(v, ctx.coach, e.name, text, ctx.user_id)
        except ValueError as err:
            st.error(str(err))
        else:
            ctx.save()
            st.rerun()


@st.dialog("Key questions", width="large", on_dismiss=state.close_dialog)
def _questions_dialog(ctx: state.PageContext, _: str = "") -> None:
    v = ctx.venture
    if v.module == Module.ALUMNI:
        st.success("All AIN EIRs agreed: this venture graduated to NextCorps.")
        return
    s = overview.status(v)
    if not s.deliverable_id:
        _graduation(ctx)
        return
    d = roadmap.deliverable(s.deliverable_id)
    p = roadmap.progress(v, d)
    st.markdown(f"#### {escape(d.title)}  \n<span class='muted'>{p.answered} of {p.total} key questions have enough "
                f"evidence · Foundry {md(escape(roadmap.position_label(v)))}</span>", unsafe_allow_html=True)
    st.caption("Disciplined Entrepreneurship steps: " + " · ".join(d.steps))
    _questions(ctx, d)
    st.divider()
    _step_check(ctx, s)


def _questions(ctx: state.PageContext, d) -> None:
    v = ctx.venture
    for q in d.questions:
        a = v.answer(q.id)
        met = roadmap.is_met(v, q)
        st.markdown(f"{'✅' if met else '⚪'} **{md(q.ask)}**")
        text = st.text_area("Your answer", a.text, height=68, key=_key(f"ans_{v.id}_{q.id}", a.text),
                            label_visibility="collapsed", placeholder="Who, how many, what they did, where it is recorded")
        if text.strip() != a.text and st.button("Save", key=f"save_{v.id}_{q.id}"):
            try:
                actions.submit_answer(v, ctx.coach, q.id, text, ctx.user_id)
            except ValueError as err:
                st.error(str(err))
            else:
                ctx.save()
                st.rerun()
        if a.text:
            grade = f"**Virtual EIR:** {a.rung.plain}" + (f" ({md(a.why)})" if a.why else "")
            st.caption(f"{grade} · needs {q.need.plain}" + (f" · {md(a.source)}" if a.source else ""))
            if not met:
                st.markdown(f"> {md(questioning.follow_up(q, a))}")
        else:
            st.caption(f"Needs at least {q.need.plain}")


def _step_check(ctx: state.PageContext, s: overview.Status) -> None:
    v = ctx.venture
    d = roadmap.deliverable(s.deliverable_id)
    if st.button(f"Check this step: {d.title}", key=f"check_{d.id}", type="primary", icon=":material/fact_check:"):
        actions.check_step(v, d.id, ctx.user_id)
        ctx.save()
        st.rerun()
    j = s.judgment
    latest = v.judgments[-1] if v.judgments else None
    if latest is not None and latest is not j and latest.review == ReviewState.PENDING:
        j = latest  # the step just passed and the venture moved on: keep its review visible
    if j is None:
        st.caption("The rules check each key question against the evidence it needs. Your Virtual EIR never marks a "
                   "step complete.")
        return
    tone = "ok" if j.verdict == Verdict.READY else "warn"
    tags = [chip(f"Last check {j.date} · {roadmap.deliverable(j.deliverable).title}: {j.verdict.value}", tone)]
    if j.review == ReviewState.PENDING:
        tags.append(chip("An AIN EIR will check this judgment", "warn"))
    elif j.review in (ReviewState.CONFIRMED, ReviewState.REOPENED):
        tags.append(chip(f"{j.review.value}: {j.reviewer}"))
    chips(*tags)
    if j.note:
        st.caption(f"EIR note: \"{md(j.note)}\"")
    for r in j.reasons:
        st.markdown(f"- {md(r)}")
    if j.consider:
        st.markdown("**If I were you, I would also consider** _(your choice)_")
        for c in j.consider:
            st.markdown(f"- {md(c)}")


def _graduation(ctx: state.PageContext) -> None:
    v = ctx.venture
    if not roadmap.roadmap_complete(v):
        st.caption("All deliverables of this module are done.")
        return
    if v.graduation == "requested":
        st.info("Graduation review (NextCorps): waiting for the AIN EIRs. All of them must agree.")
        return
    if v.graduation.startswith("returned"):
        st.warning("The EIRs returned the review: " + md(v.graduation.removeprefix("returned: ")))
    st.caption("All four deliverables are done. Asking for the review shares your answers (never your "
               "conversations) with the AIN EIRs.")
    if st.button("Ask the AIN EIRs for the graduation review", key=f"grad_{v.id}"):
        actions.request_graduation(v, ctx.user_id)
        ctx.save()
        st.rerun()


@st.dialog("Project history", width="large", on_dismiss=state.close_dialog)
def _history_dialog(ctx: state.PageContext, _: str = "") -> None:
    v = ctx.venture
    decided = overview.decisions(v)
    if decided:
        st.markdown("#### Decisions")
        for e in decided:
            st.markdown(f"- {md(escape(e.text))} <span class='muted'>· {escape(_who(v, e.by))} · {escape(e.date)}</span>",
                        unsafe_allow_html=True)
    st.markdown(f"#### All activity {source_tag('records')}", unsafe_allow_html=True)
    items = overview.recent_changes(v, limit=200, events=True)
    if not items:
        st.caption("No changes yet.")
    for r in items:
        st.markdown(f"- {md(escape(r.text))} <span class='muted'>· {escape(_who(v, r.by))} · {escape(when(r.when))}"
                    "</span>", unsafe_allow_html=True)
    st.caption("Each change your Virtual EIR makes is also listed under its reply in the chat, where you can undo it.")


@st.dialog("Add a file", width="medium", on_dismiss=state.close_dialog)
def _add_file_dialog(ctx: state.PageContext, _: str = "") -> None:
    v = ctx.venture
    st.caption("Plans, pitch decks, interview notes, research, surveys, sheets and screenshots (no code), up to "
               f"{files.MAX_MB} MB. A file with the same name becomes its next version. What a document says counts "
               "as your claim until your Virtual EIR grades the evidence."
               + (" IP-sensitive project: share business documents only." if v.ip_sensitive else ""))
    with st.container(key="ov_add"):
        upload = st.file_uploader("Upload a file", type=list(files.ACCEPTED), max_upload_size=files.MAX_MB,
                                  key=f"ov_upload_{v.id}_{state.upload_round()}", label_visibility="collapsed")
    if upload is not None:
        _save_upload(ctx, upload)
    _flash("files")
    _saved_offer(ctx)
    with st.expander("Or share a link", icon=":material/link:"):
        _link_form(ctx)


def _save_upload(ctx: state.PageContext, upload) -> None:
    """Save the file in the project folder only: the Virtual EIR reads it when the team asks."""
    v = ctx.venture
    try:
        f = actions.save_file(v, ctx.files, ctx.user_id, upload.name, upload.getvalue())
    except (ValueError, PermissionError) as err:
        state.flash("error", f"{upload.name} was not saved: {err}", where="files")
        state.next_upload_round()
    else:
        ctx.save()
        state.file_saved(f.id)
    st.rerun()


def _link_form(ctx: state.PageContext) -> None:
    v = ctx.venture
    url = st.text_input("Link", key=f"link_url_{v.id}", placeholder="https://")
    what = st.text_input("What does it show?", key=f"link_what_{v.id}",
                         placeholder="e.g. our landing page with the waitlist form")
    st.caption("Your Virtual EIR does not open links: it works from what you say the link shows.")
    if st.button("Add the link", key=f"link_add_{v.id}", disabled=not (url.strip() and what.strip())):
        try:
            actions.add_link(v, ctx.user_id, url, what)
        except ValueError as err:
            st.error(str(err))
        else:
            _done(ctx)


@st.dialog("Project files", width="large", on_dismiss=state.close_dialog)
def _files_dialog(ctx: state.PageContext, _: str = "") -> None:
    v = ctx.venture
    if st.button("Add a file", key=f"ov_files_add_{v.id}", icon=":material/add:"):
        state.open_dialog("ov_add_file")
        st.rerun()
    ordered = _ordered_files(v)
    if not ordered:
        st.caption("No files yet.")
    for f in ordered:
        _file(ctx, f)


@st.dialog("File", width="large", on_dismiss=state.close_dialog)
def _file_dialog(ctx: state.PageContext, file_id: str = "") -> None:
    f = ctx.venture.file(file_id)
    if f is None or f.latest is None:
        st.caption("This file was removed.")
        return
    _file(ctx, f, open_details=True)


def _download(ctx: state.PageContext, f, version, key: str) -> None:
    if f.kind == FileKind.LINK:
        st.link_button("Open", f.url, icon=":material/open_in_new:")
        return
    try:
        data = ctx.files.get(version.blob)
    except KeyError:
        st.caption("File missing")
        return
    name = f.name if version is f.latest else f"{PurePath(f.name).stem} (version {version.number}){PurePath(f.name).suffix}"
    st.download_button("Download", data, file_name=name, key=key, icon=":material/download:")


def _file(ctx: state.PageContext, f, open_details: bool = False) -> None:
    v = ctx.venture
    latest = f.latest
    link = f.kind == FileKind.LINK  # a link is never opened, so there is nothing to read or discuss
    shared = None if link else files.discussion(v, f)
    with st.container(border=True, key=f"file_{f.id}"):
        info, buttons = st.columns([3, 2.2], vertical_alignment="center")
        meta = [files.LABELS[f.kind]] + ([] if link else [f"version {latest.number}"]) + [
            f"{'added' if link else 'updated'} {when(latest.at)}", f"by {v.display_name(latest.by)}"]
        status = ("" if link else chip("Discussed with your Virtual EIR", "ok") if shared
                  else chip("Read by your Virtual EIR", "ok") if files.read_by_eir(f, latest)
                  else chip("Not discussed yet"))
        info.markdown(f"**{escape(f.name)}** {status}<br><span class='muted'>{escape(' · '.join(meta))}</span>",
                      unsafe_allow_html=True)
        with buttons, st.container(horizontal=True, gap="small", horizontal_alignment="right"):
            _download(ctx, f, latest, f"file_dl_{f.id}")
            if shared:
                if st.button("Open the chat", key=f"file_chat_{f.id}", icon=":material/forum:"):
                    state.go_to(state.HOME)
                    st.rerun()  # out of the dialog
            elif not link and st.button("Discuss", key=f"file_discuss_{f.id}", type="primary", icon=":material/forum:",
                                        help="Opens the chat, where your Virtual EIR reads it and discusses it with you"):
                _discuss(f.id)
        with st.expander("Details" if link else "Preview and details", expanded=open_details,
                         icon=":material/visibility:"):
            _preview(ctx, f, latest, shared)


def _preview(ctx: state.PageContext, f, latest, shared) -> None:
    v = ctx.venture
    if f.kind == FileKind.LINK:
        st.markdown(f"<a href='{escape(f.url)}' target='_blank'>{escape(f.url)}</a>", unsafe_allow_html=True)
        st.caption(f"What it shows, in your team's words: {md(latest.note or latest.summary)}")
    else:
        if files.read_by_eir(f, latest):
            st.markdown(f"**Summary by your Virtual EIR** {chip('AI', 'ai')}  \n{md(escape(latest.summary))}",
                        unsafe_allow_html=True)
        elif not shared:
            st.caption("Not read by your Virtual EIR yet: press Discuss when you want its view.")
        _content(ctx, f, latest)
    if latest.claims:
        st.markdown("**Key claims in the latest version** (claims, not evidence)\n"
                    + "\n".join(f"- {md(c)}" for c in latest.claims))
    pending = files.revision_tasks(v, f)
    if pending:
        st.caption("Open revisions: " + "; ".join(md(s.text) for s in pending))
    for version in [] if f.kind == FileKind.LINK else reversed(f.versions):
        text, button = st.columns([4, 1.3], vertical_alignment="center")
        text.markdown(f"**Version {version.number}** <span class='muted'>· {escape(v.display_name(version.by))} · "
                      f"{escape(when(version.at))}" + (f" · {version.size // 1024 + 1} KB" if version.size else "")
                      + "</span>" + (f"  \n{md(escape(version.note))}" if version.note else ""), unsafe_allow_html=True)
        if version is not latest:
            with button:
                _download(ctx, f, version, f"file_dl_{f.id}_v{version.number}")
    if shared and st.button("Discuss it again", key=f"file_again_{f.id}", icon=":material/forum:"):
        _discuss(f.id)
    sure = st.checkbox("Remove this link" if f.kind == FileKind.LINK else "Remove this file and all its versions",
                       key=f"file_rm_ok_{f.id}")
    if st.button("Remove", key=f"file_rm_{f.id}", disabled=not sure, icon=":material/delete:"):
        actions.delete_file(v, ctx.files, ctx.user_id, f.id)
        _done(ctx)


def _content(ctx: state.PageContext, f, latest) -> None:
    """A look inside the latest version: the picture, or the start of its text."""
    if f.kind == FileKind.IMAGE:
        try:
            st.image(ctx.files.get(latest.blob), width=360)
        except KeyError:
            st.caption("File missing")
        return
    body = files.text(ctx.files, f, latest).strip()
    if not body:
        st.caption("No readable text: the file may be scanned, protected or damaged.")
        return
    with st.container(height=220, border=True, key=f"file_text_{f.id}"):
        st.text(body[:PREVIEW_CHARS] + ("…" if len(body) > PREVIEW_CHARS else ""))
