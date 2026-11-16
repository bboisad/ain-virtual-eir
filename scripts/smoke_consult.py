"""Real-model check of one whole consultation on the fictional demo venture Campus Loop (in memory; nothing is saved).

Run from virtual_eir/:  python scripts/smoke_consult.py
Alice asks for the pricing consultant from the rail; the lead mentor writes the brief; Alice talks to the consultant;
the consultant writes its summary; Alice adds one line and sends it; the lead mentor replies and updates the records.
Prints every step with its time. Uses the same settings as the app (see scripts/smoke_llm.py); never prints the key.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eir import actions, changes  # noqa: E402
from eir.coach import make_coach  # noqa: E402
from eir.seed import demo_ventures  # noqa: E402
from smoke_llm import settings  # noqa: E402

STUDENT = [
    "Most movers just leave their stuff in the hallway. Why would they pay $3 to sell it?",
    "Res Life told us they fine $25 for items left in rooms, but nobody checks the hallways.",
    "So what should we test first?",
]


def step(title: str):
    print("=" * 100 + f"\n{title}\n" + "-" * 100)
    return time.perf_counter()


def main() -> int:
    coach = make_coach(settings())
    if not hasattr(coach, "client"):
        print("No model configured: fill in ~/.streamlit/secrets.toml first.")
        return 2
    v = next(x for x in demo_ventures() if x.id == "V-CAMPUS")
    print(f"Model: {coach.label} · fictional demo venture: {v.name}\n")

    start = step("Alice clicks the pricing consultant in the rail")
    c, standard = actions.request_consultant(v, coach, "m1", "pricing")
    print(f"({time.perf_counter() - start:.1f}s; standard brief used: {standard})")
    print(f"MENTOR: {v.conversation[-1].text}\n\nBRIEF ({c.requested_by}):\n{c.brief}\n\nCONSULTANT: {c.messages[0].text}")

    for text in STUDENT:
        start = step(f"Alice: {text}")
        reply = actions.consult_message(v, coach, c.id, "m1", text)
        print(f"CONSULTANT ({time.perf_counter() - start:.1f}s; proposes to end: {c.proposed_end}):\n{reply.text}")

    start = step("Alice presses End and send back: the summary to preview")
    s = actions.draft_summary(v, coach, c.id, "m1")
    print(f"({time.perf_counter() - start:.1f}s)")
    for name in ("question", "conclusions", "missing_evidence", "suggested_todos", "needs_human", "human_topic",
                 "disagreements", "out_of_scope"):
        print(f"  {name}: {getattr(s, name)}")

    start = step("Alice adds one line and sends it to the mentor")
    reply = actions.send_summary(v, coach, c.id, "m1", note="I still want to try $3 first")
    print(f"MENTOR ({time.perf_counter() - start:.1f}s):\n{reply.text}")
    for group in reply.change_groups:
        for ch in changes.changes_in(v, group):
            print(f"  changed: {ch.summary} (source: {ch.source})")
    print(f"\nConsultation status: {c.status.value}; the mentor's records now have {len(v.next_steps)} tasks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
