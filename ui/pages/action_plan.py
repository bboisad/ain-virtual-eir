"""Action Plan: what the venture believes, how it tests it, what it does.

- Assumptions (moved here from the Overview in v0.19): the riskiest first, each with its evidence for and against
  and the experiment that tests it.
- Experiments: an experiment tests one assumption (or, with the Optimize Virtual EIR, a lens). The team writes,
  before it starts, what result supports the assumption and what refutes it; starting locks those criteria. The
  Virtual EIR judges the result against them, and the evidence level comes from the method, whatever the outcome
  ("0 of 10 paid" is still rung 5).
- Tasks: finishing a task never validates anything.
"""
from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from eir import actions, experiments, modes, overview
from eir.coach.base import LeadEvent
from eir.models import Conclusion, Direction, Experiment, ExperimentStatus, LeadMode, StepStatus
from ui import state
from ui.components import chip, chips, importance_chip, md, page_title, rung_chip, status_chip


def render(ctx: state.PageContext) -> None:
    page_title("Action Plan", "What you believe, how you test it, and what you do. Agree before a test what result "
                              "would support or refute the assumption; your Virtual EIR judges the result.")
    _flash()
    _assumptions(ctx)
    _experiments(ctx)
    _tasks(ctx)


# ---- assumptions: what the venture depends on, riskiest first ----
def _assumptions(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.markdown("#### Assumptions")
    key = overview.key_assumptions(v)
    if not key:
        st.caption("No assumptions recorded yet. Your Virtual EIR writes them down as you talk.")
    for col, h in zip(st.columns(len(key)) if key else [], key):
        with col, st.container(border=True, key=f"ap_assumption_{h.id}"):
            st.markdown(f"**{h.id} · {md(h.statement)}**")
            chips(importance_chip(h.importance), rung_chip(h.rung), status_chip(h.status))
            if h.updated:
                st.caption(f"Updated {h.updated}")
            for label, direction in (("For", Direction.FOR), ("Against", Direction.AGAINST),
                                     ("Unclear", Direction.UNCLEAR)):
                items = [i for i in h.evidence_items if i.direction == direction][-2:]
                if items:
                    st.markdown(f"**{label}:**  \n" + "  \n".join(
                        f"{md(i.text)} <span class='muted'>({escape(i.rung.plain)})</span>" for i in items),
                        unsafe_allow_html=True)
            x = overview.next_test(v, h)
            st.caption(f"Tested by: {md(x.method)} ({x.status.value.lower()})" if x else "No test planned yet")
    with st.expander(f"All assumptions ({len(v.hypotheses)})", icon=":material/list:"):
        for h in v.hypotheses:
            st.markdown(f"**{h.id}** {md(h.statement)}  \n" + " ".join(
                (importance_chip(h.importance), rung_chip(h.rung), status_chip(h.status))), unsafe_allow_html=True)
        statement = st.text_input("Add an assumption", key=f"new_assumption_{v.id}",
                                  placeholder="One sentence you believe but have not proven")
        if st.button("Add", key=f"add_assumption_{v.id}", disabled=not statement.strip()):
            actions.add_assumption(v, statement, ctx.user_id)
            ctx.save()
            st.rerun()
        st.caption("Your Virtual EIR rates how much depends on it and records the evidence for and against.")


def _flash() -> None:
    f = state.pop_flash()
    if f:
        getattr(st, f[0])(f[1])


def _owners(ctx: state.PageContext) -> list[str]:
    return ["team"] + [m.id for m in ctx.venture.members]


def _due(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _tests(ctx: state.PageContext, x: Experiment) -> str:
    v = ctx.venture
    if x.assumption_id:
        h = v.hypothesis(x.assumption_id)
        return f"Tests {x.assumption_id}: {h.statement if h else '(removed)'}"
    lens = modes.lens(x.lens)
    return f"Tests the {lens.title if lens else x.lens} lens"


# ---- experiments ----
def _experiments(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.markdown("#### Experiments")
    open_ones = sorted((x for x in v.experiments if x.is_open), key=lambda x: x.status != ExperimentStatus.RUNNING)
    if not open_ones:
        st.caption("No experiment under way. Plan one below, or ask your Virtual EIR to help design it.")
    for x in open_ones:
        _experiment(ctx, x)
    _new_experiment(ctx)
    finished = [x for x in v.experiments if not x.is_open]
    if finished:
        with st.expander(f"Finished experiments ({len(finished)})", icon=":material/inventory_2:"):
            for x in reversed(finished):
                _experiment(ctx, x)


def _experiment(ctx: state.PageContext, x: Experiment) -> None:
    v = ctx.venture
    with st.container(border=True, key=f"exp_{x.id}"):
        st.markdown(f"**{md(_tests(ctx, x))}**")
        tags = [status_chip(x.status), rung_chip(x.method_rung, "Method evidence"),
                chip(f"Owner: {v.display_name(x.owner)}")]
        if x.deadline:
            tags.append(chip(f"Due {x.deadline}"))
        chips(*tags)
        if x.status == ExperimentStatus.DRAFT:
            _draft(ctx, x)
        elif x.status == ExperimentStatus.RUNNING:
            _running(ctx, x)
        else:
            _ended(ctx, x)


def _criteria(x: Experiment, locked: bool) -> None:
    lock = ":material/lock: " if locked else ""
    st.markdown(f"**Method:** {md(x.method)}  \n{lock}**Supported if:** {md(x.supported_if or '—')}  \n"
                f"{lock}**Refuted if:** {md(x.refuted_if or '—')}  \n"
                "<span class='muted'>Anything in between is inconclusive.</span>", unsafe_allow_html=True)


def _draft(ctx: state.PageContext, x: Experiment) -> None:
    v = ctx.venture
    _criteria(x, locked=False)
    missing = experiments.missing_to_start(x)
    if missing:
        st.caption("Before you start, write down " + ", ".join(missing) + ".")
    st.caption("Starting locks the criteria. To change them later, stop the experiment and start a new draft.")
    if st.button("Start the experiment", key=f"start_{x.id}", type="primary", disabled=bool(missing),
                 icon=":material/play_arrow:"):
        actions.start_experiment(v, x.id, ctx.user_id)
        ctx.save()
        st.rerun()
    with st.expander("Edit the draft", expanded=bool(missing), icon=":material/edit:"):
        _draft_form(ctx, x)


def _draft_form(ctx: state.PageContext, x: Experiment) -> None:
    v = ctx.venture
    with st.form(f"draft_{x.id}", border=False):
        method = st.text_area("Method: who, how many, what you will ask them to do", x.method, height=80)
        a, b = st.columns(2)
        supported = a.text_input("Supported if", x.supported_if, placeholder="e.g. 4 or more of the 10 prepay")
        refuted = b.text_input("Refuted if", x.refuted_if, placeholder="e.g. fewer than 2 of the 10 prepay")
        c, d = st.columns(2)
        owners = _owners(ctx)
        owner = c.selectbox("Owner", owners, index=owners.index(x.owner) if x.owner in owners else 0,
                            format_func=v.display_name)
        deadline = d.date_input("Deadline (optional)", value=_due(x.deadline), format="YYYY-MM-DD")
        saved = st.form_submit_button("Save draft")
        st.caption("If you change the method, your Virtual EIR rates its evidence level again.")
    if saved:
        fields = {name: value for name, value, old in (
            ("method", method, x.method), ("supported_if", supported, x.supported_if),
            ("refuted_if", refuted, x.refuted_if), ("owner", owner, x.owner),
            ("deadline", _iso(deadline), x.deadline)) if value.strip() != old}
        if fields:
            try:
                actions.edit_experiment(v, ctx.coach, x.id, ctx.user_id, **fields)
            except (ValueError, PermissionError) as err:
                st.error(str(err))
                return
            ctx.save()
            st.rerun()


def _running(ctx: state.PageContext, x: Experiment) -> None:
    v = ctx.venture
    _criteria(x, locked=True)
    st.caption(f"Running since {x.started_at}; the criteria are locked.")
    result = st.text_area("Result: what happened, in numbers", x.result, height=70, key=f"result_{x.id}",
                          placeholder="e.g. 2 of 10 movers prepaid $3")
    a, b, _ = st.columns([1.2, 1.6, 2])
    if a.button("Save result", key=f"save_result_{x.id}", disabled=result.strip() == x.result):
        try:
            actions.record_experiment_result(v, x.id, ctx.user_id, result)
        except ValueError as err:
            st.error(str(err))
        else:
            ctx.save()
            st.rerun()
    if b.button("Ask the Virtual EIR to judge", key=f"judge_{x.id}", type="primary", disabled=not x.result,
                icon=":material/gavel:", help="Your Virtual EIR compares the result with the criteria you agreed"):
        name = v.display_name(ctx.user_id)
        with st.spinner("Your Virtual EIR is comparing the result with your criteria…"):
            try:
                reply = actions.mentor_event(v, ctx.coach, ctx.user_id, LeadEvent("judge", x.id),
                                             note=f"{name} asked the Virtual EIR to judge the experiment: {x.method}",
                                             files=ctx.files)
            except Exception as err:  # noqa: BLE001 - keep the page usable and say what happened
                state.flash("error", f"The Virtual EIR could not judge it right now: {str(err)[:200]}")
            else:
                judged = v.experiment(x.id)
                state.flash("success" if judged.status == ExperimentStatus.CONCLUDED else "info",
                            md(reply.text.split("\n")[0]) + "  \nThe full reply is in the Virtual EIR chat.")
        ctx.save()
        st.rerun()
    with st.expander("Stop this experiment"):
        reason = st.text_input("Why do you stop it?", key=f"stop_reason_{x.id}",
                               placeholder="e.g. the criteria were too easy to meet")
        replace = st.checkbox("Open a new draft with the same method, so we can change the criteria", value=True,
                              key=f"stop_replace_{x.id}")
        if st.button("Stop", key=f"stop_{x.id}", disabled=not reason.strip()):
            actions.stop_experiment(v, x.id, ctx.user_id, reason, replace=replace)
            ctx.save()
            st.rerun()


def _ended(ctx: state.PageContext, x: Experiment) -> None:
    v = ctx.venture
    _criteria(x, locked=True)
    if x.result:
        st.markdown(f"**Result:** {md(x.result)}" + (f" _(recorded by {v.display_name(x.result_by)})_"
                                                    if x.result_by else ""))
    if x.status == ExperimentStatus.CONCLUDED:
        chips(status_chip(x.conclusion), chip(f"Judged {x.ended_at}"))
        st.caption(f"Why: {md(x.judged_why)}")
        if x.assumption_id and x.conclusion != Conclusion.NONE:
            st.caption(f"Added to {x.assumption_id} as evidence: {x.method_rung.plain}.")
    else:
        st.caption(f"Stopped {x.ended_at}: {md(x.stop_reason)}")
        nxt = next((y for y in v.experiments if y.replaces == x.id), None)
        if nxt:
            st.caption(f"Replaced by a new {nxt.status.value.lower()} experiment.")


def _clear(*keys: str) -> None:
    """Empty a form after it was used (its widgets come back with their defaults on the next run)."""
    for key in keys:
        st.session_state.pop(key, None)


def _new_experiment(ctx: state.PageContext) -> None:
    v = ctx.venture
    # Open assumptions first; a supported one can still need a stronger test.
    hypotheses = sorted(v.hypotheses, key=lambda h: not h.status.is_open)
    targets = [("assumption", h.id) for h in hypotheses]
    if v.lead_mode == LeadMode.OPTIMIZE:
        targets += [("lens", x.id) for x in modes.lenses()]

    def label(t: tuple[str, str]) -> str:
        if t[0] == "assumption":
            h = v.hypothesis(t[1])
            return f"{h.id} · {h.statement}" + ("" if h.status.is_open else f" ({h.status.value.lower()})")
        return f"Lens · {modes.lens(t[1]).title}"

    keys = {name: f"newx_{name}_{v.id}" for name in ("target", "method", "supported", "refuted", "owner", "deadline")}
    with st.expander("Plan a new experiment", icon=":material/science:"):
        if not targets:
            st.caption("Add an assumption first (Overview), or tell your Virtual EIR what you believe.")
            return
        with st.form(f"new_experiment_{v.id}", border=False):
            target = st.selectbox("What does it test?", targets, format_func=label, key=keys["target"])
            method = st.text_area("Method: who, how many, what you will ask them to do", height=80,
                                  placeholder="e.g. Offer prepaid $3 listings to 10 movers at the Residence Life table",
                                  key=keys["method"])
            a, b = st.columns(2)
            supported = a.text_input("Supported if", placeholder="e.g. 4 or more of the 10 prepay",
                                     key=keys["supported"])
            refuted = b.text_input("Refuted if", placeholder="e.g. fewer than 2 of the 10 prepay", key=keys["refuted"])
            c, d = st.columns(2)
            owner = c.selectbox("Owner", _owners(ctx), format_func=v.display_name, key=keys["owner"])
            deadline = d.date_input("Deadline (optional)", value=None, format="YYYY-MM-DD", key=keys["deadline"])
            added = st.form_submit_button("Add the experiment as a draft")
        st.caption("Your Virtual EIR rates the evidence your method can produce. The criteria lock when you start.")
    if added:
        kind, ref = target
        try:
            actions.add_experiment(v, ctx.coach, ctx.user_id, method,
                                   assumption_id=ref if kind == "assumption" else "",
                                   lens=ref if kind == "lens" else "", supported_if=supported, refuted_if=refuted,
                                   owner=owner, deadline=_iso(deadline))
        except (ValueError, PermissionError) as err:
            st.error(str(err))
            return
        ctx.save()
        _clear(*keys.values())
        st.rerun()


# ---- tasks ----
def _tasks(ctx: state.PageContext) -> None:
    v = ctx.venture
    st.markdown("#### Tasks")
    open_steps = sorted(v.open_steps(), key=lambda s: s.due_date or "9999-12-31")
    if not open_steps:
        st.caption("No open tasks.")
    for s in open_steps:
        with st.container(border=True, key=f"task_{s.id}"):
            text, done = st.columns([5, 1.4], vertical_alignment="center")
            meta = [v.display_name(s.owner)] + ([f"due {s.due_date}"] if s.due_date else [])
            if s.experiment_id and (x := v.experiment(s.experiment_id)):
                meta.append(f"for the experiment \"{x.method[:60]}\"")
            if s.file_id and (f := v.file(s.file_id)):
                meta.append(f"revision of {f.name}: your Virtual EIR checks it in the next version")
            text.markdown(f"{md(s.text)}  \n<span class='muted'>{escape(' · '.join(meta))}</span>",
                          unsafe_allow_html=True)
            with done.popover("Done…", icon=":material/check:", width="stretch"):
                result = st.text_input("What happened? (optional)", key=f"done_result_{s.id}")
                if st.button("Mark done", key=f"done_{s.id}", type="primary"):
                    actions.complete_step(v, s.id, ctx.user_id, result)
                    ctx.save()
                    st.rerun()
    _new_task(ctx)
    done = [s for s in v.next_steps if s.status == StepStatus.DONE]
    if done:
        with st.expander(f"Done ({len(done)})", icon=":material/task_alt:"):
            for s in reversed(done):
                st.markdown(f"~~{md(s.text)}~~ <span class='muted'>· {escape(v.display_name(s.done_by or s.owner))}"
                            f"{escape(': ' + s.result) if s.result else ''}</span>", unsafe_allow_html=True)


def _new_task(ctx: state.PageContext) -> None:
    v = ctx.venture
    keys = {name: f"task_{name}_{v.id}" for name in ("text", "owner", "due")}
    with st.expander("Add a task", icon=":material/add_task:"):
        with st.form(f"new_task_{v.id}", border=False):
            text = st.text_input("Task", key=keys["text"])
            a, b = st.columns(2)
            owner = a.selectbox("Owner", _owners(ctx), format_func=v.display_name, key=keys["owner"])
            due = b.date_input("Due date (optional)", value=None, format="YYYY-MM-DD", key=keys["due"])
            added = st.form_submit_button("Add task")
    if added:
        try:
            actions.add_step(v, text, owner, ctx.user_id, _iso(due))
        except (ValueError, PermissionError) as err:
            st.error(str(err))
            return
        ctx.save()
        _clear(*keys.values())
        st.rerun()
