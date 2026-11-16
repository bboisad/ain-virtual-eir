"""The two lead mentors: Launch (A) and Optimize (B). The student chooses; the system recommends.

- `recommend()`: the suggestion from the two questions asked at project creation.
- `entry_check()`: Optimize first checks that customers actually did something (rung 4+); if not, it says so and
  suggests Launch.
- `ready_for_optimize()`: Launch suggests Optimize once, when customers did something and every canvas block is graded.
- `switch()`: changes the lead mentor. All records stay; the earlier mentor's chat stays readable.
- Optimize's skeleton is six lenses (knowledge/diagnostics.json); the bottleneck is the weakest graded lens.

`customer_behavior_rung()` is a heuristic for these suggestions; the mentor makes the call in the conversation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .clock import today
from .models import (CANVAS_BLOCKS, SYSTEM, Conclusion, Event, EventKind, ExperimentStatus, Goal, LeadMode, Message,
                     MessageKind, ModeSwitch, Rung, Traction, Venture, VentureType)

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
CUSTOMER_BEHAVIOR = Rung.DID
CUSTOMER_QUESTIONS = ("cd_interviews", "pd_commitment", "bp_assumptions")  # Foundry questions on what customers did
CUSTOMER_LENSES = ("customer", "business_model")
SHORT_NAMES = {LeadMode.LAUNCH: "Launch", LeadMode.OPTIMIZE: "Optimize"}
NAMES = {mode: f"{name} Virtual EIR" for mode, name in SHORT_NAMES.items()}
DESCRIPTIONS = {
    LeadMode.LAUNCH: ("Turn your idea into a practical venture plan. Your Virtual EIR guides you through the AIN "
                      "Foundry roadmap, challenges your assumptions, and helps you identify what to test next."),
    LeadMode.OPTIMIZE: ("Strengthen an existing venture. Your Virtual EIR reviews your evidence, helps you identify "
                        "the most important bottleneck, and guides you in designing an experiment to test it."),
}
GREETING = {  # shown before the first message, and the scripted mentor's opening line
    LeadMode.LAUNCH: "Hi, I'm your Launch Virtual EIR, an AI advisor. Tell me what problem you are solving and who has it.",
    LeadMode.OPTIMIZE: ("Hi, I'm your Optimize Virtual EIR, an AI advisor. Before we optimize anything: what have customers "
                        "already done? Who signed up, tried or paid, and how many?"),
}


@dataclass(frozen=True)
class Lens:
    id: str
    title: str
    order: int
    question: str
    probes: tuple[str, ...] = ()


@lru_cache
def diagnostics() -> dict:
    return json.loads((KNOWLEDGE / "diagnostics.json").read_text(encoding="utf-8"))


@lru_cache
def lenses() -> tuple[Lens, ...]:
    items = (Lens(x["id"], x["title"], int(x["order"]), x["question"], tuple(x.get("probes", [])))
             for x in diagnostics()["lenses"])
    return tuple(sorted(items, key=lambda x: x.order))


def lens_ids() -> tuple[str, ...]:
    return tuple(x.id for x in lenses())


def lens(lens_id: str) -> Lens | None:
    return next((x for x in lenses() if x.id == lens_id), None)


def recommend(traction: Traction | None, goal: Goal | None, venture_type: VentureType) -> LeadMode:
    """Optimize only when customers already did something and the team wants to improve it. Research spin-outs start
    with Launch: their IP and regulatory questions go to humans."""
    if venture_type == VentureType.RESEARCH:
        return LeadMode.LAUNCH
    return LeadMode.OPTIMIZE if traction == Traction.YES and goal == Goal.IMPROVE else LeadMode.LAUNCH


def why_recommended(traction: Traction | None, goal: Goal | None, venture_type: VentureType) -> str:
    """One sentence on the recommendation, shown when the team picks its lead mentor."""
    if venture_type == VentureType.RESEARCH:
        return ("Research spin-outs start with the Launch Virtual EIR; IP and regulatory questions go to human experts "
                "(UR Ventures, I-Corps).")
    if recommend(traction, goal, venture_type) == LeadMode.OPTIMIZE:
        return "Customers already signed up, tried or paid, and you want to improve what runs."
    if traction == Traction.YES:
        return "Customers already use it, but you want to shape the plan first."
    if goal == Goal.IMPROVE:
        return ("You want to improve something, but no customer has signed up, tried or paid yet. Optimizing needs "
                "that behavior first; the Launch Virtual EIR helps you get it.")
    return "You are shaping an idea into a plan."


def customer_behavior_rung(v: Venture) -> Rung:
    """Strongest recorded evidence of what customers did: Foundry answers about customer behavior, the customer and
    business-model lenses, and experiments that supported their assumption."""
    rungs = [v.answer(q).rung for q in CUSTOMER_QUESTIONS]
    rungs += [v.lenses[x].rung for x in CUSTOMER_LENSES if x in v.lenses]
    rungs += [x.method_rung for x in v.experiments
              if x.status == ExperimentStatus.CONCLUDED and x.conclusion == Conclusion.SUPPORTED]
    return Rung(max(rungs, default=Rung.NONE))


def entry_check(v: Venture) -> tuple[bool, Rung]:
    """Optimize's first check: did customers do something (rung 4+)? Returns (ok, best rung so far)."""
    best = customer_behavior_rung(v)
    return best >= CUSTOMER_BEHAVIOR, best


def entry_message(best: Rung) -> str:
    return diagnostics()["entry"]["message"].format(best=best.label if best else "none recorded")


def ready_for_optimize(v: Venture) -> bool:
    """Launch suggests Optimize once: customers did something and every canvas block is graded."""
    return (v.lead_mode == LeadMode.LAUNCH and not v.optimize_suggested_on
            and customer_behavior_rung(v) >= CUSTOMER_BEHAVIOR
            and all(v.canvas[b].rung > Rung.NONE for b in CANVAS_BLOCKS))


def mark_optimize_suggested(v: Venture) -> None:
    v.optimize_suggested_on = today()


def switch(v: Venture, to: LeadMode, by: str, reason: str = "") -> ModeSwitch:
    """Change the lead mentor. Records stay as they are; the earlier mentor's chat stays readable (Venture.thread)."""
    to = LeadMode(to)
    if to == v.lead_mode:
        raise ValueError(f"You are already working with the {NAMES[to]}")
    s = ModeSwitch(today(), v.lead_mode, to, by, reason.strip())
    v.mode_history.append(s)
    v.lead_mode = to
    v.conversation.append(Message(SYSTEM, f"Switched from the {NAMES[s.from_mode]} to the {NAMES[to]}. Every record "
                                          "stays, and the earlier conversation is still readable.",
                                  mentor=to, kind=MessageKind.EVENT))
    v.timeline.append(Event(today(), EventKind.DECISION,
                            f"Switched to the {NAMES[to]}" + (f": {s.reason}" if s.reason else ""), by))
    return s


def suggest_bottleneck(v: Venture) -> str | None:
    """The weakest graded lens; on a tie, the one closer to the customer. None until a lens is graded."""
    graded = [x for x in lenses() if x.id in v.lenses]
    if not graded:
        return None
    return min(graded, key=lambda x: (v.lenses[x.id].rung, x.order)).id


def optimize_complete(v: Venture) -> bool:
    """Optimize is done when the bottleneck is named and one experiment on it has a conclusion."""
    b = v.diagnosis.bottleneck
    return bool(b) and any(x.lens == b and x.status == ExperimentStatus.CONCLUDED for x in v.experiments)
