"""Mentor Brief: a consent-based summary for a human AIN EIR, built from the venture's records (never the chats)."""
from __future__ import annotations

from . import consult, modes, overview, roadmap
from .models import ConsultationStatus, Direction, HypothesisStatus, Rung, Venture

DEFAULT_TOPICS = ("Preparing our next EIR Foundry session", "Choosing the next experiment", "Fundraising or negotiation",
                  "IP or regulatory expertise")
EVIDENCE = Rung.SAID  # from "customers said" up, a record counts as evidence in the brief


def topics(v: Venture) -> list[str]:
    return ([v.handoff] if v.handoff else []) + list(DEFAULT_TOPICS)


def _strongest(h) -> str:
    items = sorted(h.evidence_items, key=lambda i: i.rung, reverse=True)
    if not items:
        return ""
    i = items[0]
    return f"{i.text} ({i.rung.label}, {'against' if i.direction == Direction.AGAINST else 'for'})"


def mentor_brief(v: Venture, topic: str) -> str:
    entries = overview.evidence_map(v)
    evidence = [f"- {e.name}: {e.text} ({e.rung.label})" for e in entries if e.text and e.rung >= EVIDENCE]
    evidence += [f"- {h.statement}: {_strongest(h)}" for h in v.hypotheses
                 if h.rung >= EVIDENCE and _strongest(h)]
    open_ones = [f"- {h.statement} ({h.status.value}; {h.rung.label})" for h in overview.key_assumptions(v, limit=5)
                 if h.status.is_open]
    open_ones += [f"- {e.name}: {e.text} ({e.rung.label})" for e in entries if e.text and e.rung < EVIDENCE]
    refuted = [f"- {h.statement}" for h in v.hypotheses if h.status == HypothesisStatus.REFUTED]
    tests = [f"- {x.method} ({x.status.value.lower()}; supported if {x.supported_if or '?'}; refuted if "
             f"{x.refuted_if or '?'})" for x in v.experiments if x.is_open]
    steps = [f"- {v.display_name(s.owner)}: {s.text}" for s in v.open_steps()]
    flagged = [f"- {consult.name_of(c.consultant)} consultant: {c.summary.human_topic or c.question}"
               for c in v.consultations if c.status == ConsultationStatus.DONE and c.summary and c.summary.needs_human]
    disagreements = [f"- {d.topic}: {v.display_name(d.a_member)} vs {v.display_name(d.b_member)}"
                     for d in v.open_disagreements()]
    team = ", ".join(f"{m.name} ({m.background})" for m in v.members)
    status = overview.status(v)

    sections = [
        f"# Human EIR brief: {v.name}",
        f"**Topic:** {topic}  \n**Virtual EIR:** {modes.NAMES[v.lead_mode]} (AI) · **Position:** {status.position}"
        f"  \n**Roadmap:** {roadmap.info(v.module).name} · **Type:** {v.type.value}  \n**Team:** {team}"
        + (f"  \n**Next EIR session:** {v.next_eir_session}" if v.next_eir_session else "")
        + f"  \n**Suggested EIR expertise:** {roadmap.expertise_for(topic)}",
        "_Shared with the team's consent. Contains no conversation transcripts"
        + (" and no technical details (IP-sensitive venture)._" if v.ip_sensitive else "._"),
        f"**Current focus:** {status.focus} ({status.focus_rung.label})",
        "## Roadmap checklist", *_checklist(v),
        "## Evidence so far", *(evidence or ["- None yet"]),
        "## Open assumptions and claims", *(open_ones or ["- None recorded"]),
    ]
    if refuted:
        sections += ["## Refuted so far", *refuted]
    if tests:
        sections += ["## Experiments under way", *tests]
    if flagged:
        sections += ["## Flagged for a human by the AI consultants", *flagged]
    if disagreements:
        sections += ["## Team disagreements", *disagreements]
    sections += [
        "## Open next steps", *(steps or ["- None"]),
        "## Questions for the human EIR",
        f"1. What is the biggest risk we are missing on: {topic.lower()}?",
        "2. What evidence would you want to see before our next milestone?",
        "3. Who at AIN or outside should we talk to next?",
    ]
    return "\n".join(sections)


def _checklist(v: Venture) -> list[str]:
    d = roadmap.current_deliverable(v)
    if d is None:
        return ["- All deliverables of this module are done"]
    rows = [f"- {'✅' if roadmap.is_met(v, q) else '⚪'} {q.ask} — {v.answer(q.id).rung.label}"
            + (f" ({v.answer(q.id).text})" if v.answer(q.id).text else "") for q in d.questions]
    return [f"**{d.title}**", *rows]
