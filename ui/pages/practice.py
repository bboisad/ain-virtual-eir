"""Practice: rehearse with AI characters (a target customer, a competition judge, a challenger) before the real
conversation. The rules live in eir/practice.py; what each character sees in eir/access.py (rule 8).

The page has three states:
- home: "Recommended now", the three characters (each says what it knows) and the team's sessions;
- a session: the conversation; beside it the goal, tips, what the character knows, pitch timing and hints;
- its feedback: scores, what worked, three fixes and the checks against the records. "Send to my Virtual EIR" sends the
  feedback, never the conversation.

The setup dialog opens pre-filled from a character card, "Change settings" or a mentor's suggestion. A practice
session is the team's own: nothing in it is evidence, and nothing in it changes the records.
"""
from __future__ import annotations

from html import escape as _escape

import streamlit as st

from eir import actions, overview, practice
from eir.models import CHARACTER, Difficulty, Message, Rehearsal, RehearsalStatus
from ui import state
from ui.components import avatar, character_avatar, chip, chips, md, page_title, score_bars, when

MAX_SUGGESTIONS = 3
LONG = 140  # a longer prepared message shows as its start and its length in words


def escape(text: str) -> str:
    """Text inside HTML elements ("You're" stays readable; attributes here never hold free text)."""
    return _escape(text, quote=False)


def render(ctx: state.PageContext) -> None:
    v = ctx.venture
    r = v.rehearsal(state.rehearsal()) if state.rehearsal() else None
    if state.rehearsal() and r is None:  # e.g. discarded by a teammate
        state.close_rehearsal()
    if r is None:
        _home(ctx)
    elif r.status == RehearsalStatus.OPEN:
        _session(ctx, r)
    else:
        _feedback(ctx, r)
    if state.practice_setup() and not state.dialog():
        _setup(ctx)


def _flash() -> None:
    f = state.pop_flash()
    if f:
        getattr(st, f[0])(f[1])


def _who(s: practice.CharacterSpec, title: str, lines: str = "", size: int = 42) -> str:
    """Avatar and name block (HTML)."""
    return (f"<div class='practice-who'><img src='{character_avatar(s)}' width='{size}'><div>{title}"
            f"{'<br>' + lines if lines else ''}</div></div>")


def _start(ctx: state.PageContext, character: str, scenario: str, difficulty: Difficulty,
           file_ids: tuple[str, ...] | list[str] = (), assumption_id: str = "") -> None:
    v = ctx.venture
    with st.spinner(f"Getting the {practice.name_of(character).lower()} ready…"):
        try:
            r = actions.start_practice(v, ctx.coach, ctx.user_id, character, scenario, difficulty, tuple(file_ids),
                                       assumption_id, files=ctx.files)
        except (ValueError, PermissionError) as err:
            state.close_practice_setup()
            state.flash("error", str(err))
            st.rerun()
    ctx.save()
    state.open_rehearsal(r.id)
    st.rerun()


# ---- home ----
def _home(ctx: state.PageContext) -> None:
    page_title("Practice", "Rehearse with AI characters before the real conversation. They are practice partners: "
                           "nothing they say is evidence, and your Virtual EIR sees a session's feedback only if you send "
                           "it.")
    _flash()
    st.markdown("<style>" + "".join(f".st-key-pcard_{s.id}{{border-top:4px solid {s.color} !important}}"
                                    for s in practice.characters()) + "</style>", unsafe_allow_html=True)
    _recommended(ctx)
    for column, s in zip(st.columns(len(practice.characters()), gap="medium"), practice.characters()):
        with column:
            _character_card(ctx, s)
    _sessions(ctx)


def _recommended(ctx: state.PageContext) -> None:
    v = ctx.venture
    rec = practice.recommended(v)
    s = practice.spec(rec.character)
    sc = s.scenario(rec.scenario)
    running = next((r for r in practice.in_progress(v) if (r.character, r.scenario) == (rec.character, rec.scenario)),
                   None)
    with st.container(border=True, key="practice_recommended"):
        text, buttons = st.columns([3.2, 1.2], vertical_alignment="center")
        with text:
            st.markdown("<div class='eyebrow'>Recommended now</div>", unsafe_allow_html=True)
            st.markdown(_who(s, f"<b>{escape(rec.reason)}</b>", f"<span class='muted'>{escape(s.name)} · "
                                                                 f"{escape(sc.title)} · {rec.difficulty.value} · about "
                                                                 f"{sc.minutes} min{_reads(v, rec.file_ids)}</span>"),
                        unsafe_allow_html=True)
        with buttons:
            if running is not None:
                st.button("Continue your session", key="practice_rec_continue", type="primary", width="stretch",
                          icon=":material/play_arrow:", on_click=state.open_rehearsal, args=(running.id,))
            elif st.button("Start", key="practice_rec_start", type="primary", icon=":material/play_arrow:",
                           width="stretch"):
                _start(ctx, rec.character, rec.scenario, rec.difficulty, rec.file_ids)
            st.button("Change settings", key="practice_rec_setup", width="stretch", icon=":material/tune:",
                      on_click=state.open_practice_setup, args=(f"{rec.character}/{rec.scenario}",))


def _reads(v, file_ids) -> str:
    names = [f.name for fid in file_ids if (f := v.file(fid)) is not None]
    return f" · reads {escape(', '.join(names))}" if names else ""


def _character_card(ctx: state.PageContext, s: practice.CharacterSpec) -> None:
    v = ctx.venture
    rec = practice.recommended(v)
    with st.container(border=True, key=f"pcard_{s.id}"):
        st.markdown(_who(s, f"<b>{escape(s.name)}</b>", "<span class='muted'>AI role-play · fictional</span>"),
                    unsafe_allow_html=True)
        st.markdown(md(s.purpose))
        st.markdown(f"<div class='practice-knows'><b>Knows:</b> {escape(s.knows)}</div>", unsafe_allow_html=True)
        st.caption(f"{len(s.scenarios)} scenarios · about {s.scenarios[0].minutes} min",
                   help=" · ".join(x.title for x in s.scenarios))
        scores = practice.scores_over_time(v, s.id)
        if scores:
            st.caption("Your scores so far: " + " → ".join(f"{x:.1f}" for x in scores[-4:]))
        scenario = rec.scenario if rec.character == s.id else s.scenarios[0].id
        st.button("Practise", key=f"practise_{s.id}", icon=":material/record_voice_over:", width="stretch",
                  on_click=state.open_practice_setup, args=(f"{s.id}/{scenario}",))


def _sessions(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.markdown("#### Your practice sessions")
    items = practice.history(v)
    if not items:
        st.caption("None yet. Sessions stay with your team. Your Virtual EIR sees a session's feedback only if you send "
                   "it, and never the conversation.")
        return
    for r in items:
        s = practice.spec(r.character)
        f = r.feedback
        with st.container(border=True, key=f"psession_{r.id}"):
            text, button = st.columns([5, 1.2], vertical_alignment="center")
            score = chip(f"{f.overall:.1f} / 5", "ok" if f.overall >= 4 else "warn" if f.overall < 3 else "") if f \
                else chip("In progress", "warn")
            sent = chip("Sent to your Virtual EIR") if r.shared_at else ""
            text.markdown(_who(s, f"<b>{escape(practice.character_label(r))}</b> · "
                                  f"{escape(practice.scenario_of(r).title)} · {r.difficulty.value} {score}{sent}",
                               f"<span class='muted'>{escape(when(r.started_at))} · "
                               f"{escape(v.display_name(r.started_by))}</span>", size=34), unsafe_allow_html=True)
            if f and (f.fixes or f.verdict):
                text.caption(f"Fix first: {md(f.fixes[0] if f.fixes else f.verdict)}")
            button.button("Open" if f else "Continue", key=f"psession_open_{r.id}", width="stretch",
                          on_click=state.open_rehearsal, args=(r.id,))


# ---- the setup dialog ----
def _initial(v) -> tuple[str, str, str]:
    """(character, scenario, assumption id) the dialog opens with."""
    character, scenario, assumption = (state.practice_setup().split("/") + ["", ""])[:3]
    ids = [c.id for c in practice.characters()]
    character = character if character in ids else practice.recommended(v).character
    scenarios = [x.id for x in practice.spec(character).scenarios]
    return character, scenario if scenario in scenarios else scenarios[0], assumption


@st.dialog("Start a practice session", width="large", on_dismiss=state.close_practice_setup)
def _setup(ctx: state.PageContext) -> None:
    v = ctx.venture
    character0, scenario0, assumption0 = _initial(v)
    character = st.segmented_control("Who do you want to practise with?", [c.id for c in practice.characters()],
                                     default=character0, required=True, format_func=practice.name_of,
                                     key=f"ps_character_{v.id}")
    s = practice.spec(character or character0)
    st.markdown(_who(s, f"<b>{escape(s.name)}</b>", f"<span class='muted'>{escape(s.purpose)}</span>"),
                unsafe_allow_html=True)
    ids = [x.id for x in s.scenarios]
    scenario = st.radio("Scenario", ids, index=ids.index(scenario0) if scenario0 in ids else 0,
                        format_func=lambda x: s.scenario(x).title, captions=[x.description for x in s.scenarios],
                        key=f"ps_scenario_{v.id}_{s.id}")
    sc = s.scenario(scenario)
    level = st.segmented_control("Difficulty", [d.value for d in Difficulty], default=Difficulty.REALISTIC.value,
                                 required=True, key=f"ps_difficulty_{v.id}")
    difficulty = Difficulty(level or Difficulty.REALISTIC.value)
    st.caption(s.how(difficulty))
    file_ids: list[str] = []
    if s.sees != practice.SEGMENT:
        options = [f.id for f in v.files if f.latest is not None]
        if options:
            file_ids = st.multiselect("Material they read", options,
                                      default=[x for x in practice.default_files(v, s.id) if x in options],
                                      format_func=lambda fid: v.file(fid).name, key=f"ps_files_{v.id}_{s.id}",
                                      placeholder="None: " + ("your Overview only" if s.sees == practice.SUBMISSION
                                                              else "your records and file summaries only"),
                                      help="Your project files. They read the summary" + (
                                          "" if v.ip_sensitive else " and the start of the text") + ".")
        else:
            st.caption("No project files yet. Share your pitch deck in the Virtual EIR chat and the judge can read it.")
    assumption = ""
    if sc.needs_assumption:
        hs = [h.id for h in overview.key_assumptions(v, limit=len(v.hypotheses))]
        if hs:
            assumption = st.selectbox("The assumption to attack", hs,
                                      index=hs.index(assumption0) if assumption0 in hs else 0,
                                      format_func=lambda hid: f"{hid} · {v.hypothesis(hid).statement}",
                                      key=f"ps_assumption_{v.id}")
        else:
            st.warning("Record an assumption first (Overview), or choose another scenario.")
    with st.container(border=True, key="ps_knows"):
        st.markdown(f"**What the {s.name.lower()} knows:** {md(_knows(v, s, file_ids))}")
        st.caption("A fictional AI character, never a real person. Nothing it says is evidence, and your records "
                   "don't change. Afterwards a practice coach gives you feedback.")
    running = next((r for r in practice.in_progress(v) if r.character == s.id), None)
    start, other = st.columns([1.4, 2], vertical_alignment="center")
    if start.button("Start practice", key=f"ps_start_{v.id}", type="primary", icon=":material/play_arrow:",
                    width="stretch", disabled=sc.needs_assumption and not assumption):
        _start(ctx, s.id, sc.id, difficulty, file_ids, assumption)
    if running is not None:
        other.button(f"Continue your session from {when(running.started_at)} instead", key=f"ps_continue_{v.id}",
                     type="tertiary", on_click=state.open_rehearsal, args=(running.id,))


def _knows(v, s: practice.CharacterSpec, file_ids, persona: str = "") -> str:
    names = [f"\"{f.name}\"" for fid in file_ids if (f := v.file(fid)) is not None]
    if s.sees == practice.SEGMENT:
        who = persona or "one person from your customer segment"
        return f"only who they are ({who}). They know nothing about your idea."
    ip = " Technical details are withheld (IP-sensitive project)." if v.ip_sensitive else ""
    if s.sees == practice.SUBMISSION:
        return "your Overview" + (f" and {', '.join(names)}" if names else "") + ", like a judge who read your " \
               "submission. Not your chats." + ip
    return ("all your records: assumptions and evidence, experiments, tasks and your files' summaries"
            + (f", plus {', '.join(names)}" if names else "") + ". Never your chats." + ip)


# ---- a session ----
def _session(ctx: state.PageContext, r: Rehearsal) -> None:
    s, sc = practice.spec(r.character), practice.scenario_of(r)
    _session_head(ctx, r, s, sc)
    _flash()
    chat, side = st.columns([2.3, 1], gap="medium")
    with side:
        _side_panel(ctx, r, s, sc)
    with chat:
        _conversation(ctx, r, s)


def _session_head(ctx: state.PageContext, r: Rehearsal, s: practice.CharacterSpec, sc: practice.Scenario) -> None:
    name = practice.first_name(r)
    title = f"<b>{escape(name)}</b> · {escape(s.name.lower())}" if name else f"<b>{escape(s.name)}</b>"
    tags = chip("AI role-play") + chip(sc.title) + chip(r.difficulty.value)
    lines = f"{tags}<br><span class='muted'>{escape(r.persona)}</span>" if r.persona else tags
    with st.container(key="practice_head"):
        head, end, back = st.columns([4, 1.7, 1.5], vertical_alignment="center")
        head.markdown(_who(s, title, lines, size=46), unsafe_allow_html=True)
        spoke = bool(practice.team_messages(r))
        if end.button("End and get feedback", key=f"pend_{r.id}", type="primary", icon=":material/grading:",
                      width="stretch", disabled=not spoke,
                      help="A practice coach, not the character, writes your feedback" if spoke else "Say something "
                                                                                                    "first"):
            _end(ctx, r)
        back.button("Back to Practice", key=f"pback_{r.id}", icon=":material/arrow_back:", width="stretch",
                    on_click=state.close_rehearsal, help="The session stays in progress: continue it any time.")


def _end(ctx: state.PageContext, r: Rehearsal) -> None:
    with st.spinner("The practice coach is writing your feedback…"):
        try:
            actions.end_practice(ctx.venture, ctx.coach, r.id, ctx.user_id, files=ctx.files)
        except (ValueError, PermissionError) as err:
            state.flash("error", str(err))
    ctx.save()
    st.rerun()


def _message(ctx: state.PageContext, r: Rehearsal, s: practice.CharacterSpec, m: Message) -> None:
    v = ctx.venture
    character = m.author == CHARACTER
    member = None if character else v.member(m.author)
    with st.chat_message("assistant" if character else "user",
                         avatar=character_avatar(s) if character else avatar(v, m.author)):
        name = practice.character_label(r) if character else (member.name if member else m.author)
        st.caption(f"{name} · {when(m.created_at)}")
        st.markdown(md(m.text))
        sc = practice.scenario_of(r)
        team = practice.team_messages(r)
        if sc.pitch_seconds and team and m is team[0]:
            t = practice.estimate(m.text, sc.pitch_seconds)
            chips(chip(f"Your pitch: {t.label}", "warn" if t.over else "ok"))


def _conversation(ctx: state.PageContext, r: Rehearsal, s: practice.CharacterSpec) -> None:
    v = ctx.venture
    label = practice.first_name(r) or f"The {s.name.lower()}"
    transcript = st.container(height=470, key="practice_transcript", autoscroll=True, border=False)
    with transcript:
        for m in r.messages:
            _message(ctx, r, s, m)
    if practice.awaiting_reply(r):
        st.caption(f"{label} has not replied to your last message yet.")
        if st.button("Ask again", key=f"pretry_{r.id}", icon=":material/refresh:"):
            with transcript, st.spinner(f"{label} is thinking…"):
                try:
                    actions.practice_retry(v, ctx.coach, r.id, ctx.user_id, files=ctx.files)
                except Exception as err:  # noqa: BLE001 - keep the page usable and say what happened
                    state.flash("error", f"{label} could not reply: {str(err)[:200]}")
            ctx.save()
            st.rerun()
    if r.wrapped_up:
        with st.container(border=True, key="practice_wrapped"):
            st.markdown(f"**{md(label)} has wrapped up.** Get your feedback now, or keep going if you have more to say.")
            with st.container(horizontal=True, gap="small"):
                if st.button("Get my feedback", key=f"pfeedback_{r.id}", type="primary", icon=":material/grading:"):
                    _end(ctx, r)
                if st.button("Keep going", key=f"pkeep_{r.id}"):
                    actions.keep_practising(v, r.id, ctx.user_id)
                    ctx.save()
                    st.rerun()
        return
    picked = _suggestions(ctx, r)
    if v.ip_sensitive:
        st.caption("IP-sensitive project: keep technical details out of your answers.")
    text = st.chat_input(_placeholder(r, s), key=f"practice_input_{r.id}")
    if text and text.strip():
        picked = text
    if picked:
        _send(ctx, r, s, picked, transcript)


def _placeholder(r: Rehearsal, s: practice.CharacterSpec) -> str:
    if s.sees == practice.SEGMENT:
        return f"Ask {practice.first_name(r) or 'them'} a question…"
    if practice.scenario_of(r).pitch_seconds and not practice.team_messages(r):
        return "Type or paste your pitch…"
    return f"Answer the {s.name.lower()}…"


def _suggestions(ctx: state.PageContext, r: Rehearsal) -> str:
    """Prepared messages for the fictional demo ventures, so the demo runs without typing."""
    examples = ctx.coach.practice_suggestions(ctx.venture, r, ctx.user_id)[:MAX_SUGGESTIONS]
    if not examples:
        return ""
    picked = ""
    with st.expander("Prepared messages (demo)", icon=":material/bolt:"):
        for i, text in enumerate(examples):
            label = text if len(text) <= LONG else f"{text[:LONG].rsplit(' ', 1)[0]}… ({len(text.split())} words)"
            if st.button(md(label), key=f"psuggest_{r.id}_{i}", width="stretch"):
                picked = text
    return picked


def _send(ctx: state.PageContext, r: Rehearsal, s: practice.CharacterSpec, text: str, transcript) -> None:
    v = ctx.venture
    label = practice.first_name(r) or f"The {s.name.lower()}"
    sent = len(r.messages)
    with transcript:
        with st.chat_message("user", avatar=avatar(v, ctx.user_id)):
            st.markdown(md(text))
        with st.chat_message("assistant", avatar=character_avatar(s)), st.spinner(f"{label} is thinking…"):
            try:
                actions.practice_message(v, ctx.coach, r.id, ctx.user_id, text, files=ctx.files)
            except Exception as err:  # noqa: BLE001 - say what happened; a stored message is never lost
                state.flash("error", f"Your message was kept, but {label} could not reply: {str(err)[:200]}. Press "
                                     "**Ask again**." if len(r.messages) > sent else str(err))
    ctx.save()
    st.rerun()


def _side_panel(ctx: state.PageContext, r: Rehearsal, s: practice.CharacterSpec, sc: practice.Scenario) -> None:
    v = ctx.venture
    with st.container(border=True, key="practice_side"):
        st.markdown("<div class='eyebrow'>Your goal</div>", unsafe_allow_html=True)
        st.markdown(md(sc.goal))
        if sc.pitch_seconds:
            timing = practice.pitch_timing(r)
            if timing is None:
                words = round(sc.pitch_seconds / 60 * practice.WORDS_PER_MINUTE)
                st.caption(f"Aim for about {words} words: {practice.clock(sc.pitch_seconds)} at a calm pace.")
            else:
                chips(chip(f"Your pitch: {timing.label}", "warn" if timing.over else "ok"))
        st.markdown("<div class='eyebrow'>Tips</div>", unsafe_allow_html=True)
        st.markdown("\n".join(f"- {md(t)}" for t in s.tips))
        st.markdown(f"<div class='eyebrow'>What {escape(practice.first_name(r) or 'the ' + s.name.lower())} "
                    "knows</div>", unsafe_allow_html=True)
        knows = md(_knows(v, s, r.file_ids, r.persona))
        st.caption(knows[:1].upper() + knows[1:])
        _hints(ctx, r)
    _discard(ctx, r)


def _hints(ctx: state.PageContext, r: Rehearsal) -> None:
    v = ctx.venture
    if st.button("Stuck? Get a hint", key=f"phint_{r.id}", icon=":material/lightbulb:", width="stretch",
                 help="A whisper from the practice coach. The character never sees it; your feedback counts hints."):
        with st.spinner("The practice coach is thinking…"):
            try:
                actions.practice_hint(v, ctx.coach, r.id, ctx.user_id, files=ctx.files)
            except (ValueError, PermissionError) as err:
                state.flash("error", str(err))
        ctx.save()
        st.rerun()
    for h in reversed(r.hints):
        st.markdown(f"<div class='hint-note'>{escape(h)}</div>", unsafe_allow_html=True)
    if r.hints:
        st.caption("Only your team sees hints, never the character.")


def _discard(ctx: state.PageContext, r: Rehearsal) -> None:
    with st.popover("Discard this session", icon=":material/delete:", width="stretch", key=f"pdiscard_menu_{r.id}"):
        st.caption("Deletes this practice session and its messages. Nothing else changes.")
        if st.button("Discard", key=f"pdiscard_{r.id}", type="primary"):
            actions.delete_practice(ctx.venture, r.id, ctx.user_id)
            ctx.save()
            state.close_rehearsal()
            st.rerun()


# ---- feedback ----
def _feedback(ctx: state.PageContext, r: Rehearsal) -> None:
    v = ctx.venture
    s, sc, f = practice.spec(r.character), practice.scenario_of(r), r.feedback
    _flash()
    with st.container(border=True, key="practice_feedback"):
        head, score = st.columns([4, 1.1], vertical_alignment="center")
        head.markdown(_who(s, f"<span class='eyebrow'>Feedback</span><br><b>{escape(practice.character_label(r))}</b>",
                           f"{escape(sc.title)} · {r.difficulty.value} · {practice.minutes(r)} min · "
                           f"{escape(v.display_name(r.started_by))}<br><span class='muted'>Written by the practice "
                           f"coach (AI) · {escape(when(f.written_at))}</span>", size=46), unsafe_allow_html=True)
        score.markdown(f"<div class='score-big'>{f.overall:.1f}<span> / 5</span></div>", unsafe_allow_html=True)
        if f.verdict:
            st.markdown(f"**{md(f.verdict)}**")
        if f.simplified:
            st.caption("Simplified feedback: keyword checks, because no AI is connected.")
        st.markdown(score_bars(s, f), unsafe_allow_html=True)
        good, fix = st.columns(2, gap="medium")
        with good:
            st.markdown("<div class='eyebrow'>What worked</div>", unsafe_allow_html=True)
            st.markdown("\n".join(f"- {md(x)}" for x in f.strengths) or "_Nothing stood out yet._")
        with fix:
            st.markdown("<div class='eyebrow'>Fix these first</div>", unsafe_allow_html=True)
            st.markdown("\n".join(f"{i}. {md(x)}" for i, x in enumerate(f.fixes, 1)))
        _feedback_list("Toughest questions → a stronger answer", f.tough_questions)
        _feedback_list("Weak spots found", f.problems)
        if f.checks:
            _feedback_list("Worth checking with real customers", f.checks)
            st.caption(f"{practice.first_name(r) or 'The customer'} is made up: check these with real customers "
                       "before you rely on them.")
        if f.unsupported_claims:
            st.warning("**Claims your records don't support**\n" + "\n".join(f"- {md(x)}" for x in f.unsupported_claims),
                       icon=":material/report:")
        if f.hints_used:
            st.caption(f"You used {f.hints_used} hint{'s' if f.hints_used > 1 else ''} from the practice coach.")
    _feedback_actions(ctx, r)
    with st.expander(f"The conversation ({len(r.messages)} messages)", icon=":material/forum:"):
        for m in r.messages:
            _message(ctx, r, s, m)


def _feedback_list(title: str, items: list[str]) -> None:
    if items:
        st.markdown(f"<div class='eyebrow'>{escape(title)}</div>", unsafe_allow_html=True)
        st.markdown("\n".join(f"- {md(x)}" for x in items))


def _feedback_actions(ctx: state.PageContext, r: Rehearsal) -> None:
    v = ctx.venture
    again, send, back = st.columns(3)
    if again.button("Practise again", key=f"pagain_{r.id}", icon=":material/replay:", width="stretch",
                    help="Same character and settings" + (", a new customer" if practice.first_name(r) else "")):
        with st.spinner(f"Getting the {practice.name_of(r.character).lower()} ready…"):
            try:
                new = actions.practice_again(v, ctx.coach, r.id, ctx.user_id, files=ctx.files)
            except (ValueError, PermissionError) as err:
                state.flash("error", str(err))
                st.rerun()
        ctx.save()
        state.open_rehearsal(new.id)
        st.rerun()
    with send:
        if r.shared_at:
            st.button("See your Virtual EIR's reply", key=f"preply_{r.id}", icon=":material/forum:", width="stretch",
                      on_click=state.go_to, args=("Mentor",))
        else:
            with st.popover("Send to my Virtual EIR", icon=":material/send:", width="stretch", key=f"psend_menu_{r.id}"):
                st.caption("Your Virtual EIR receives this feedback, never the conversation, and may add to-dos from it. "
                           "Practice is not evidence.")
                note = st.text_input("One line for your Virtual EIR (optional)", max_chars=practice.NOTE_LIMIT,
                                     key=f"pnote_{r.id}", placeholder="e.g. The money question froze me")
                if st.button("Send", key=f"psend_{r.id}", type="primary", icon=":material/send:"):
                    _share(ctx, r, note)
    back.button("Back to Practice", key=f"pdone_back_{r.id}", icon=":material/arrow_back:", width="stretch",
                on_click=state.close_rehearsal)
    if r.shared_at:
        note = f": \"{md(r.shared_note)}\"" if r.shared_note else ""
        st.caption(f"Sent to your Virtual EIR {when(r.shared_at)} by {v.display_name(r.shared_by)}{note}. Your Virtual EIR "
                   "received the feedback, not the conversation.")


def _share(ctx: state.PageContext, r: Rehearsal, note: str) -> None:
    v = ctx.venture
    with st.spinner("Your Virtual EIR is reading the feedback…"):
        try:
            actions.share_practice(v, ctx.coach, r.id, ctx.user_id, note, files=ctx.files)
            state.flash("success", "Sent. Your Virtual EIR replied on the Virtual EIR page.")
        except Exception as err:  # noqa: BLE001 - say what happened; nothing is lost
            state.flash("error", f"The feedback was sent, but your Virtual EIR could not reply yet: {str(err)[:200]}. "
                                 "Press **Ask the Virtual EIR again** on the Virtual EIR page." if r.shared_at else str(err))
    ctx.save()
    st.rerun()
