"""Real-model check of the lead mentor on the fictional demo venture Campus Loop (in memory; nothing is saved).

Run from virtual_eir/:  python scripts/smoke_lead.py
For each scenario it prints the mentor's reply, every action it called (with the result the app gave back), and the
records it changed; then it starts the $3 prepay experiment, records "2 of 10 movers prepaid" and asks the mentor to
judge it against the criteria. Uses the same settings as the app (see scripts/smoke_llm.py). Never prints the API key.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eir import actions, changes  # noqa: E402
from eir.coach import LeadEvent, make_coach  # noqa: E402
from eir.seed import demo_ventures  # noqa: E402
from smoke_llm import settings  # noqa: E402

SCENARIOS = [
    ("m2", "Bob reports interview results",
     "I did 2 more interviews. 4 of 5 total said they'd only use it if it's free."),
    ("m1", "Alice asks for a pricing expert", "Can a pricing expert look at whether $3 is the right fee?"),
    ("m1", "Alice inflates a claim", "Everyone we talked to loved it - I'm sure they'll pay $3."),
]


def main() -> int:
    s = settings()
    coach = make_coach(s)
    if not hasattr(coach, "client"):
        print("No model configured: fill in ~/.streamlit/secrets.toml first.")
        return 2
    runs = []
    original = coach.client.run_tools

    def recording(*args, **kwargs):
        run = original(*args, **kwargs)
        runs.append(run)
        return run

    coach.client.run_tools = recording
    v = next(x for x in demo_ventures() if x.id == "V-CAMPUS")
    print(f"Model: {coach.label} · fictional demo venture: {v.name}\n")
    for author, title, text in SCENARIOS:
        print("=" * 100 + f"\n{title}\n{v.display_name(author)}: {text}\n" + "-" * 100)
        start = time.perf_counter()
        reply = actions.mentor_message(v, coach, author, text)
        print(f"MENTOR ({time.perf_counter() - start:.1f}s, tool mode {coach.client.tool_mode}):\n{reply.text}\n")
        for call, result in runs[-1].calls:
            print(f"  action {call.name}({call.args}) -> {result}")
        for group in reply.change_groups:
            for c in changes.changes_in(v, group):
                print(f"  changed: {c.summary}")
        if reply.consultation_id:
            c = v.consultation(reply.consultation_id)
            print(f"  consultation opened with {c.consultant}; brief:\n    " + c.brief.replace("\n", "\n    "))
        print()

    print("=" * 100 + "\nAlice starts the $3 prepay test, records 2 of 10, and asks the mentor to judge\n" + "-" * 100)
    actions.start_experiment(v, "X-fee", "m1")
    actions.record_experiment_result(v, "X-fee", "m1", "2 of 10 movers prepaid $3")
    start = time.perf_counter()
    reply = actions.mentor_event(v, coach, "m1", LeadEvent("judge", "X-fee"),
                                 note="Alice asked the mentor to judge the experiment.")
    x, h = v.experiment("X-fee"), v.hypothesis("H2")
    print(f"MENTOR ({time.perf_counter() - start:.1f}s):\n{reply.text}\n")
    print(f"  experiment: {x.status.value}, conclusion {x.conclusion.value or '-'} ({x.judged_why})")
    print(f"  assumption H2: {h.status.value}, strongest evidence {h.rung.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
