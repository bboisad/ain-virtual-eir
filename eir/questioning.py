"""Questioning engine (design v0.2 §3.3): the Virtual EIR keeps asking until a claim has evidence.

Every claim is questioned in a fixed order — be specific → evidence → alternatives → consequence → test —
and the stage depends on how far up the evidence ladder the team's answer already is.
One or two questions at a time; the engine never answers for the student.
Used by the scripted coach directly; the AI mentor gets the same chain as instructions (memory.lead_context).
"""
from __future__ import annotations

from . import roadmap
from .models import Answer, Rung, Venture


def next_question(v: Venture) -> str | None:
    """The next question the Virtual EIR should ask about the current deliverable (markdown), or None."""
    gaps = roadmap.weakest(v, limit=1)
    if not gaps:
        d = roadmap.current_deliverable(v)
        if d is None:
            return None
        return (f"Every key question of **{d.title}** has the evidence it needs. "
                "Press **Check this step** on the Overview, and I will tell you what else I would consider.")
    q, a = gaps[0]
    d = roadmap.deliverable_of(q.id)
    return f"**{d.title}** · {q.ask}\n\n{follow_up(q, a)}"


def follow_up(q: roadmap.Question, a: Answer) -> str:
    """The next question in the chain for one answer, based on how far up the evidence ladder it is."""
    if a.rung == Rung.NONE:
        return ("Be specific: who exactly, how many, and in what situation? "
                "A name or a number is worth more than an adjective.")
    said = f"You said: \"{a.text.rstrip('.')}\"."
    if a.rung == Rung.ASSERTION:
        return (f"{said} How do you know? Is that something customers told you, something they did, "
                "or your own belief? Right now it counts as an assertion.")
    if a.rung == Rung.SECONDARY:
        return (f"{said} That is desk research, and estimates (including mine) can be wrong. "
                "Who can you talk to this week to check it with real customers? Say how many.")
    if a.rung == Rung.SAID:
        return (f"{said} People said it. Did any of them actually do something: sign up, switch, "
                "pre-order, pay? Agree in advance what result would prove you wrong.")
    return (f"{said} Good evidence so far. If this turned out to be wrong, what would happen to your "
            f"venture? This step needs {q.need.label}.")
