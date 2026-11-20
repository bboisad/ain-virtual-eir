"""What the lead mentor remembers, rendered as text. Everything is read from the Venture, so it follows the records.

- `briefing()`     : the Mentor page's opening lines (what to do now, last time, open consultations).
- `lead_context()` : the lead mentor's knowledge of the venture, for its system prompt.
- `window()`       : the latest part of the mentor chat for the model; `ensure_day_summaries()` covers earlier days.
- `open_threads()` : unresolved items to bring up before new advice.
"""
from __future__ import annotations

from datetime import date, datetime

from . import access, consult, files, modes, overview, practice, roadmap
from .models import EIR, SYSTEM, DaySummary, Experiment, FocusKind, LeadMode, Message, MessageKind, Rung, Venture

MAX_FILES = 8  # project files described in the mentor's context (newest)
PRACTICE_SHARED = 2  # practice feedback the team sent, described in the mentor's context (newest)


def open_threads(v: Venture, limit: int = 3) -> list[str]:
    """Unresolved items the EIR should bring up before giving new advice (markdown bullets):
    disagreements first, then roadmap claims without evidence, then open actions."""
    threads = [f"- Open disagreement on **{d.topic.lower()}**: {v.display_name(d.a_member)} says "
               f"\"{d.a_says}\", {v.display_name(d.b_member)} says \"{d.b_says}\"."
               for d in v.open_disagreements()]
    threads += [f"- Roadmap: \"{q.ask}\" is at {a.rung.label.lower()}; this step needs {q.need.label.lower()}."
                for q, a in roadmap.weakest(v, limit=2) if a.rung > Rung.NONE]
    threads += [f"- {v.display_name(s.owner)} still has an open action: {s.text}." for s in v.open_steps()]
    return threads[:limit]


# ---- the lead mentor's briefing, context and chat window ----
WINDOW_MESSAGES = 30  # the model sees the latest messages of the current mentor's chat ...
WINDOW_CHARS = 16_000  # ... within this budget; day summaries cover the rest


def last_time(v: Venture) -> tuple[str, str] | None:
    """(date label, summary) of the latest day before today, or the latest archived v0.15 session."""
    past = [d for d in v.day_summaries if d.day < date.today().isoformat()]
    if past:
        d = max(past, key=lambda d: d.day)
        return d.label, d.summary
    if v.sessions:
        return v.sessions[-1].date, v.sessions[-1].summary
    return None


def action_line(v: Venture, item) -> str:
    """One next action (an experiment or a task) in one line."""
    if isinstance(item, Experiment):
        due = f", due {item.deadline}" if item.deadline else ""
        return (f"Experiment ({item.status.value.lower()}{due}): {item.method}. "
                f"Supported if {item.supported_if or '?'}; refuted if {item.refuted_if or '?'}.")
    due = f", due {item.due_date}" if item.due_date else ""
    return f"{v.display_name(item.owner)}: {item.text}{due}"


def briefing(v: Venture) -> list[str]:
    """The Mentor page's opening lines: what to do now (the same data as the Overview's focus card), then last time and
    open consultations. Students read it, so the evidence has its plain name."""
    st = overview.status(v)
    lines = [f"**Current focus:** {st.focus} _({st.focus_rung.plain})_"]
    nxt = overview.next_actions(v, limit=1)
    if nxt:
        lines.append(f"**Next:** {action_line(v, nxt[0])}")
    lt = last_time(v)
    if lt:
        lines.append(f"**Last time ({lt[0]}):** {lt[1]}")
    lines += [f"**Open consultation:** {consult.name_of(c.consultant)} · {c.question}"
              for c in consult.open_consultations(v)]
    return lines


def window(v: Venture) -> tuple[list[dict], dict[str, str]]:
    """The current lead mentor's chat for the model, oldest first, and the map from tag to message id.
    Team messages are tagged [m1], [m2], … so record updates can cite them. Notes from the app read "(note) …"."""
    kept, total = [], 0
    for m in reversed(v.thread(v.lead_mode)[-WINDOW_MESSAGES:]):
        total += len(m.text)
        if kept and total > WINDOW_CHARS:
            break
        kept.append(m)
    refs: dict[str, str] = {}
    out: list[dict] = []
    for m in reversed(kept):
        if m.author == EIR:
            role, content = "assistant", m.text
        elif m.author == SYSTEM or m.kind == MessageKind.EVENT:
            role, content = "user", f"(note) {m.text}"
        else:
            tag = f"m{len(refs) + 1}"
            refs[tag] = m.id
            role, content = "user", f"[{tag}] {v.display_name(m.author)}: {m.text}{attachment(v, m)}"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] == "assistant":  # chats sent to the model start with the team
        out.pop(0)
    return out, refs


def attachment(v: Venture, m: Message) -> str:
    """The project file a team message carries, as the model sees it: id, name, version and summary."""
    f = v.file(m.file_id) if m.file_id else None
    if f is None:
        return ""
    version = f.version(m.file_version) or f.latest
    text = f"\n(attached: {f.id} \"{f.name}\", {files.LABELS[f.kind].lower()}, version {version.number}"
    if version.number > 1:
        text += ", a new version of an earlier file"
    if not f.kind.readable or not version.chars:
        text += "; not readable in this version: ask the team what it shows"
    return text + (f". Summary: {version.summary}" if version.summary else "") + ")"


def _files_text(v: Venture) -> str:
    rows = []
    for f in v.files[-MAX_FILES:]:
        latest = f.latest
        if latest is None:
            continue
        row = (f"- ({f.id}) \"{f.name}\" [{files.LABELS[f.kind].lower()}; version {latest.number}; "
               f"{v.display_name(latest.by)}]: {latest.summary or '(no summary)'}")
        if latest.claims:
            row += " Claims: " + "; ".join(latest.claims)
        if len(f.versions) > 1:
            row += f" Previous version's summary: {f.versions[-2].summary or '(none)'}"
        pending = files.revision_tasks(v, f)
        if pending:
            row += " Open revision tasks: " + "; ".join(f"({s.id}) {s.text}" for s in pending)
        rows.append(row)
    return ("PROJECT FILES (the team's own documents: claims, not evidence; read_file opens the text):\n"
            + "\n".join(rows)) if rows else ""


def add_note(messages: list[dict], text: str) -> None:
    """Append a note from the app (not from the team) as the latest user turn."""
    content = f"(note) {text}"
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + content
    else:
        messages.append({"role": "user", "content": content})


def _local_day(ts: str) -> date | None:
    try:
        return datetime.fromisoformat(ts).astimezone().date()
    except ValueError:
        return None


def ensure_day_summaries(v: Venture, coach) -> list[DaySummary]:
    """Summarize each earlier day of the mentor chat once: the briefing's "last time", and context for long chats."""
    today_d, done = date.today(), {d.day for d in v.day_summaries}
    by_day: dict[date, list[Message]] = {}
    for m in v.conversation:
        d = _local_day(m.created_at)
        if d is not None and d < today_d and d.isoformat() not in done:
            by_day.setdefault(d, []).append(m)
    added = []
    for d, msgs in sorted(by_day.items()):
        if not any(m.author not in (EIR, SYSTEM) for m in msgs):
            continue
        label = f"{d:%b} {d.day}"
        s = DaySummary(d.isoformat(), label, coach.summarize_day(v, label, msgs), msgs[-1].mentor or LeadMode.LAUNCH,
                       len(msgs))
        v.day_summaries.append(s)
        added.append(s)
    return added


def _foundry_text(v: Venture) -> str:
    m, d = roadmap.info(v.module), roadmap.current_deliverable(v)
    if d is None:
        return f"FOUNDRY: {m.name}. All deliverables of this module are done."
    rows = []
    for q in d.questions:
        a = v.answer(q.id)
        rows.append(f"- ({q.id}; step {q.step or 'Foundry item'}) [{a.rung.label}; needs {q.need.label}] {q.ask}"
                    + (f" Team's answer: {a.text}" if a.text else ""))
    j = roadmap.last_judgment(v, d.id)
    latest = f"\nLatest step check: {j.verdict.value} ({j.date}; {j.review.value})" if j else ""
    return (f"FOUNDRY: {m.name} · {d.title} (Disciplined Entrepreneurship steps: {', '.join(d.steps)})\n"
            f"Position: {roadmap.position_label(v)}\nKEY QUESTIONS (id; step) [current; required]:\n"
            + "\n".join(rows) + latest
            + "\nOnly the team presses 'Check this step' and the rules judge it. Never say a step is complete.")


def _lens_text(v: Venture) -> str:
    rows = []
    for x in modes.lenses():
        g = v.lenses.get(x.id)
        rows.append(f"- ({x.id}) {x.title} [{g.rung.label if g else 'not graded'}]: {x.question}"
                    + (f" Now: {g.summary}" if g and g.summary else ""))
    b = modes.lens(v.diagnosis.bottleneck)
    return ("LENSES (grade each, then name the bottleneck):\n" + "\n".join(rows)
            + f"\nBOTTLENECK: {f'{b.title} ({v.diagnosis.why})' if b else 'not named yet'}")


def _flags(v: Venture) -> str:
    flags = []
    if v.lead_mode == LeadMode.OPTIMIZE and not any(m.author == EIR for m in v.thread(LeadMode.OPTIMIZE)):
        ok, best = modes.entry_check(v)
        flags.append(f"ENTRY CHECK: the strongest recorded customer behavior is {best.label if best else 'none'}."
                     + ("" if ok else " That is below rung 4: unless the team now reports real customer behavior, "
                                      "say so plainly and suggest the Launch mentor (suggest_mode_switch)."))
    if modes.ready_for_optimize(v):
        flags.append("SWITCH SUGGESTION: customers did something and every canvas block is graded. Suggest the "
                     "Optimize mentor once (suggest_mode_switch); the team decides.")
    return "FLAGS:\n" + "\n".join(f"- {f}" for f in flags) if flags else ""


def _team_description(v: Venture) -> str:
    """The project intro and core content the team wrote on the Overview: its claims, never evidence."""
    p = v.profile
    rows = [(label, text) for label, text in (("Who it serves", p.customer), ("Problem", p.problem),
                                                ("Solution", p.solution), ("Business model", p.revenue)) if text]
    if not rows:
        return ""
    return ("THE TEAM'S OWN DESCRIPTION (their words on the Overview; claims, not evidence):\n"
            + "\n".join(f"- {label}: {text}" for label, text in rows))


def lead_context(v: Venture) -> str:
    """Everything the lead mentor knows about the venture, for its system prompt. Never consultation transcripts or
    practice conversations: only returned summaries and the practice feedback the team sent."""
    st = overview.status(v)
    team = "; ".join(f"{m.first_name} = {m.name} ({m.background}" + (f"; {m.experience}" if m.experience else "") + ")"
                     for m in v.members)
    ip = ("\nIP-SENSITIVE: university-owned IP. Never ask for or repeat technical details of the technology."
          if v.ip_sensitive else "")
    focus = f" (kind {v.focus.kind.value}, ref {v.focus.ref})" if v.focus.kind != FocusKind.NONE else " (not set yet)"
    parts = [f"VENTURE: {v.name}: {v.description}\nType: {v.type.value}{ip}\nTEAM (address people by first name): {team}",
             _team_description(v),
             f"LEAD MENTOR: you are the {modes.NAMES[v.lead_mode]}",
             f"CURRENT FOCUS: {st.focus} [{st.focus_rung.label}]{focus}"]
    if v.lead_mode == LeadMode.LAUNCH:
        parts += [_foundry_text(v), "CANVAS (block [rung]: text):\n"
                  + "\n".join(f"- {b} [{e.rung.label}]: {e.text or '(empty)'}" for b, e in v.canvas.items())]
    else:
        parts.append(_lens_text(v))
    assumptions = []
    for h in v.hypotheses:
        ev = "; ".join(f"{i.direction.value} ({int(i.rung)}) {i.text}" for i in h.evidence_items[-4:]) or "none yet"
        assumptions.append(f"- ({h.id}) [importance {h.importance.name.lower()}; {h.rung.label}; {h.status.value}] "
                           f"{h.statement}. Evidence: {ev}")
    parts.append("ASSUMPTIONS (id [importance; strongest evidence; conclusion]):\n" + ("\n".join(assumptions) or "- none"))
    parts.append("EXPERIMENTS:\n" + ("\n".join(
        f"- ({x.id}) [{x.status.value}] tests {x.assumption_id or x.lens}: {x.method}. Supported if: "
        f"{x.supported_if or '?'}. Refuted if: {x.refuted_if or '?'}. Method evidence: {x.method_rung.label}."
        + (f" Result: {x.result}." if x.result else "")
        + (f" Conclusion: {x.conclusion.value} ({x.judged_why})." if x.conclusion.value else "")
        for x in v.experiments) or "- none"))
    parts.append("TASKS:\n" + ("\n".join(
        f"- ({s.id}) [{s.status.value}] {v.display_name(s.owner)}: {s.text}" + (f"; due {s.due_date}" if s.due_date else "")
        + (f"; result: {s.result}" if s.result else "")
        + (f"; revision of file {s.file_id}" if s.file_id else "") for s in v.next_steps) or "- none"))
    parts.append(_files_text(v))
    parts.append("OPEN CONSULTATIONS (do NOT give your own conclusion on these topics; point the team back to the "
                 "consultant):\n" + ("\n".join(f"- ({c.id}) {consult.name_of(c.consultant)}: {c.question}"
                                               for c in consult.open_consultations(v)) or "- none"))
    returned = [c for c in v.consultations if c.summary is not None][-3:]
    if returned:
        parts.append("RETURNED CONSULTATIONS (summaries only; cite as consult:<id>):\n"
                     + "\n\n".join(f"(consult:{c.id})\n{access.lead_view_of_consultation(c)}" for c in returned))
    sent = practice.shared(v)[-PRACTICE_SHARED:]
    if sent:
        parts.append("PRACTICE FEEDBACK THE TEAM SENT YOU (feedback only, never the conversation; practice is not "
                     "evidence; cite as practice:<id>):\n"
                     + "\n\n".join(f"(practice:{r.id})\n{access.lead_view_of_practice(v, r)}" for r in sent))
    recent = overview.recent_changes(v)
    if recent:
        parts.append("RECENT RECORD CHANGES:\n" + "\n".join(f"- {r.text}" for r in recent))
    days = sorted(v.day_summaries, key=lambda d: d.day)[-7:]
    if days:
        parts.append("EARLIER DAYS:\n" + "\n".join(f"- {d.label}: {d.summary}" for d in days))
    elif v.sessions:
        parts.append("EARLIER SESSIONS:\n" + "\n".join(f"- {s.date}: {s.summary}" for s in v.sessions[-5:]))
    if v.learning_log:
        parts.append("LEARNING LOG (the students' own insights):\n"
                     + "\n".join(f"- {v.display_name(e.by)}: {e.text}" for e in v.learning_log[-5:]))
    disagreements = v.open_disagreements()
    if disagreements:
        parts.append("OPEN DISAGREEMENTS BETWEEN MEMBERS:\n" + "\n".join(
            f"- {d.topic}: {v.display_name(d.a_member)} says \"{d.a_says}\"; {v.display_name(d.b_member)} says "
            f"\"{d.b_says}\"" for d in disagreements))
    parts.append("QUESTION CHAIN (question every claim in this order, one or two questions at a time):\n"
                 + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(roadmap.question_chain())))
    parts.append("CONSULTANTS YOU CAN BRING IN:\n" + "\n".join(f"- {c.id}: {c.name}. {c.scope}"
                                                              for c in consult.consultants()))
    parts.append("PRACTICE SESSIONS YOU CAN SUGGEST (suggest_practice; the team practises on its own):\n" + "\n".join(
        f"- {c.id}/{s.id}: {c.name}, {s.title}. {s.description}" for c in practice.characters() for s in c.scenarios))
    parts.append(_flags(v))
    return "\n\n".join(p for p in parts if p)
