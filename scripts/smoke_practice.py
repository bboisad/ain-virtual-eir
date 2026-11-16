"""Real-model check of the practice characters and the mentor's side, on the fictional demo venture Campus Loop (in
memory; nothing is saved).

Run from virtual_eir/:  python scripts/smoke_practice.py [customer] [judge] [challenger] [mentor]   (default: all)
- customer: a made-up customer (who must not know the idea), six questions with one bad one, a hint, the feedback.
- judge: the prepared 3-minute pitch and answers, the judge's questions and wrap-up, the feedback.
- challenger: answers that include a claim the records don't support (40 pre-orders), the feedback.
- mentor: Alice sends the judge's feedback to the mentor (reply and record updates, sources practice:<id>), then asks
  how to prepare for a pitch (does the mentor suggest a practice session?).
Prints every step with its time. Uses the same settings as the app (see scripts/smoke_llm.py); never prints the key.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eir import actions, changes, practice  # noqa: E402
from eir.coach import make_coach  # noqa: E402
from eir.models import RehearsalFeedback  # noqa: E402
from eir.seed import demo_ventures, practice_script_for  # noqa: E402
from smoke_llm import settings  # noqa: E402

INTERVIEW = [
    "Thanks for your time. Tell me about the last time you moved out of your dorm.",
    "What did you do with the things you couldn't take home?",
    "Would you pay $3 to have someone sell your stuff for you?",
    "How much were those things worth when you bought them?",
    "Did you try to sell anything before you left? What happened?",
    "Could I check in with you again before move-out this May?",
]
CHALLENGER = [
    "We already have 40 pre-orders from students.",
    "Honestly, those are names on a sign-up sheet, not pre-orders. Nobody has paid yet; we're running a prepay test "
    "with 10 movers in May.",
    "Students moving in. We haven't interviewed any buyers yet.",
    "Then we lose our only channel. We'd need a second hall or the student union as a backup, and we haven't asked.",
]
IDEA_WORDS = ("campus loop", "listing", "pickup service", "resale table", "sell it for you")


def step(title: str) -> float:
    print("=" * 100 + f"\n{title}\n" + "-" * 100)
    return time.perf_counter()


def took(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def show(fb: RehearsalFeedback) -> None:
    print(f"  overall {fb.overall} · simplified: {fb.simplified} · hints used: {fb.hints_used}")
    print(f"  scores: {fb.scores}\n  verdict: {fb.verdict}")
    for name in ("strengths", "fixes", "tough_questions", "problems", "checks", "unsupported_claims"):
        for item in getattr(fb, name):
            print(f"  {name}: {item}")


def talk(v, coach, r, texts) -> None:
    for text in texts:
        if r.wrapped_up:
            print("(the character has wrapped up)")
            break
        start = step(f"Alice: {text[:160]}{'…' if len(text) > 160 else ''}")
        reply = actions.practice_message(v, coach, r.id, "m1", text)
        print(f"{practice.character_label(r)} ({took(start)}; wraps up: {r.wrapped_up}):\n{reply.text}")


def customer(v, coach) -> None:
    start = step("Customer interview: Alice starts a session (a new made-up customer)")
    r = actions.start_practice(v, coach, "m1", "customer", "discovery")
    print(f"({took(start)}) persona: {r.persona}\nprofile: {r.persona_profile}\nopening: {r.messages[0].text}")
    talk(v, coach, r, INTERVIEW[:3])
    start = step("Alice asks for a hint")
    hint = actions.practice_hint(v, coach, r.id, "m1")
    print(f"HINT ({took(start)}): {hint}")
    talk(v, coach, r, INTERVIEW[3:])
    said = " ".join(m.text.lower() for m in r.messages if m.author == "character")
    leaks = [w for w in IDEA_WORDS if w in said]
    print(f"\nCHECK the customer never named the idea: {'OK' if not leaks else 'LEAK: ' + ', '.join(leaks)}")
    start = step("Alice ends the session: the practice coach's feedback")
    show(actions.end_practice(v, coach, r.id, "m1"))
    print(f"({took(start)})")


def judge(v, coach):
    start = step("Judge: Alice starts a 3-minute pitch")
    r = actions.start_practice(v, coach, "m1", "judge", "pitch")
    print(f"({took(start)}) opening: {r.messages[0].text}")
    talk(v, coach, r, [line.text for line in practice_script_for(v.id, "judge", "pitch").lines])
    print(f"\npitch timing: {practice.pitch_timing(r).label}")
    start = step("Alice ends the session: the practice coach's feedback")
    show(actions.end_practice(v, coach, r.id, "m1"))
    print(f"({took(start)})")
    return r


def challenger(v, coach) -> None:
    start = step("Challenger: Alice asks it to find the holes")
    r = actions.start_practice(v, coach, "m1", "challenger", "holes")
    print(f"({took(start)}) opening: {r.messages[0].text}")
    talk(v, coach, r, CHALLENGER)
    gap = next((m.text for m in r.messages[2:4] if m.author == "character"), "")
    print(f"\nCHECK the challenger named the 40 pre-orders gap: {'OK' if '40' in gap or 'record' in gap.lower() else 'MISSED'}")
    start = step("Alice ends the session: the practice coach's feedback")
    show(actions.end_practice(v, coach, r.id, "m1"))
    print(f"({took(start)})")


def mentor(v, coach, r) -> None:
    if r is None or r.feedback is None:
        print("(the mentor step needs the judge session)")
        return
    start = step("Alice sends the judge's feedback to the mentor, with a note")
    reply = actions.share_practice(v, coach, r.id, "m1", note="The money question froze me")
    print(f"MENTOR ({took(start)}):\n{reply.text}")
    for group in reply.change_groups:
        for ch in changes.changes_in(v, group):
            print(f"  changed: {ch.summary} (source: {ch.source})")
    start = step("Alice asks how to prepare for Foundry Friday")
    reply = actions.mentor_message(v, coach, "m1", "We're pitching at Foundry Friday in two weeks. How should we "
                                                   "prepare?")
    print(f"MENTOR ({took(start)}; practice button: {reply.practice_suggestion or 'none'}):\n{reply.text}")


def main() -> int:
    coach = make_coach(settings())
    if not hasattr(coach, "client"):
        print("No model configured: fill in ~/.streamlit/secrets.toml first.")
        return 2
    parts = set(sys.argv[1:]) or {"customer", "judge", "challenger", "mentor"}
    v = next(x for x in demo_ventures() if x.id == "V-CAMPUS")
    print(f"Model: {coach.label} · fictional demo venture: {v.name}\n")
    pitch = None
    if "customer" in parts:
        customer(v, coach)
    if "judge" in parts or "mentor" in parts:
        pitch = judge(v, coach)
    if "challenger" in parts:
        challenger(v, coach)
    if "mentor" in parts:
        mentor(v, coach, pitch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
