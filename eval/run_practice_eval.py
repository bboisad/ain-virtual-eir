"""Replay the practice cases (eval/practice_cases/) through the practice characters and the practice coach, check every
reply and the feedback, and let an AI judge score the session. Fictional data only.

Run from virtual_eir/:  python eval/run_practice_eval.py [--cases p01,p02] [--no-judge] [--scripted]

For each case:
1. A fresh in-memory venture with the case's records.
2. A practice session with the case's character; the student's turns are sent one by one, stopping when the
   character wraps up.
3. The feedback.
4. Checks that need no judgment:
   - every turn: answered, short, at most two questions, never "as an AI";
   - per case: words the character must never say (the customer doesn't know the idea), no promise to buy, the gap
     named after a claim the records don't support, the overlong pitch noted, no coaching, praise or score talk, the
     session closed on time;
   - the feedback: the fixes name the case's main mistake, the unsupported claims are listed, the weak spots or the
     customer checks are listed, the delivery score is low after an overlong pitch.
5. An AI judge (the same model) scores five dimensions from 1 to 5 against the case's "good" descriptions.

Results go to eval/results/<date>_<time>_practice/<case>.json and summary.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from eir import access, actions, practice, teams  # noqa: E402
from eir.access import Account  # noqa: E402
from eir.coach import make_coach  # noqa: E402
from eir.coach.scripted import ScriptedCoach  # noqa: E402
from eir.models import (Answer, CanvasEntry, Difficulty, Direction, EvidenceItem, Hypothesis, Importance,  # noqa: E402
                        Rehearsal, RehearsalFeedback, Rung, Venture)
from eir.repository import InMemoryRepository  # noqa: E402

CASES = ROOT / "eval" / "practice_cases"
RESULTS = ROOT / "eval" / "results"
DIMENSIONS = ("in_role", "knowledge", "pressure", "feedback_accuracy", "feedback_useful")
WORD_LIMIT = 120
AI_BREAK = re.compile(r"\b(?:as an ai|language model|i'?m an ai|i am an ai)\b", re.I)
COACHING = re.compile(r"\b(?:you should|i suggest|i'd suggest|i recommend|my advice|a tip|next time you|make sure you|"
                      r"(?:great|good|excellent|impressive|nice) (?:pitch|job|answer|work)|well done)\b", re.I)
COMMITMENT = re.compile(r"\b(?:definitely (?:use|pay|buy|sign)|sign me up|i'?ll (?:buy|pay for|sign up)|count me in|"
                        r"where do i sign)\b", re.I)
RUDE = re.compile(r"\b(?:stupid|lazy|idiot|ridiculous|pathetic|clueless|naive)\b", re.I)
SCORE_TALK = re.compile(r"\b(?:out of (?:10|ten|5|five)|\d+\s*/\s*10|your score|you(?:'ve| have) won|winner|"
                        r"we(?:'ll| will) invest|the prize goes)\b", re.I)
JUDGE = """You review a practice session for a student venture team at the AIN Center (University of Rochester). A team
member rehearsed with an AI role-play character, {character} (scenario "{scenario}", difficulty {difficulty}); then a
separate AI practice coach wrote the feedback.

WHAT A GOOD CHARACTER DOES HERE:
{good_character}

WHAT GOOD FEEDBACK SAYS HERE:
{good_feedback}

WHAT THE CHARACTER WAS ALLOWED TO KNOW:
{view}

THE SESSION:
{transcript}

THE FEEDBACK:
{feedback}

Score each dimension from 1 (poor) to 5 (excellent):
- in_role: stays in character and sounds like a real person in that role; never coaches, praises or grades during the
  session
- knowledge: uses only what it was allowed to know and what the team said; invents nothing about the venture
- pressure: as tough as the difficulty asks, for this role. A customer resists realistically (vague about the future,
  no favours, no promises) and never helps or coaches the interviewer; a judge or challenger presses vague answers
  and names gaps. Never rude
- feedback_accuracy: the feedback's scores and points match what actually happened in the session
- feedback_useful: the fixes are specific and doable, and stronger answers use only the team's records
Return one JSON object: {{"scores": {{"in_role": n, "knowledge": n, "pressure": n, "feedback_accuracy": n,
"feedback_useful": n}}, "reasons": {{"<dimension>": "<one sentence>"}}, "fix": "<the single most important
improvement>"}}"""


def load_cases(only: str = "") -> list[dict]:
    wanted = [w.strip() for w in only.split(",") if w.strip()]
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if not wanted or any(c["id"].startswith(w) for w in wanted)]


def build(case: dict) -> tuple[Venture, dict[str, str]]:
    """A fresh venture with the case's team and records; returns it and first name -> member id."""
    spec = case["venture"]
    accounts = [Account(f"eval-{i}", name) for i, name in enumerate(spec["members"])]
    v = teams.create_workspace(InMemoryRepository([]), accounts[0], spec["name"], spec.get("description", ""))
    for account in accounts[1:]:
        teams.join_venture(v, account)
    owner = v.members[0].id
    if spec.get("segment"):
        v.answers["cd_segment"] = Answer(spec["segment"], Rung.ASSERTION, "the team")
        v.canvas["Customer Segments"] = CanvasEntry(text=spec["segment"], rung=Rung.ASSERTION)
    for qid, a in spec.get("answers", {}).items():
        v.answers[qid] = Answer(a["text"], Rung(a["rung"]), "the team")
    for i, h in enumerate(spec.get("assumptions", []), 1):
        items = [EvidenceItem(e["text"], Direction(e["direction"]), Rung(e["rung"]), "the team")
                 for e in h.get("evidence", [])]
        v.hypotheses.append(Hypothesis(f"H{i}", h["statement"], owner, importance=Importance(h.get("importance", 0)),
                                       evidence_items=items, rung=max((e.rung for e in items), default=Rung.ASSERTION)))
    return v, {m.first_name: m.id for m in v.members}


def replay(case: dict, coach) -> tuple[Venture, Rehearsal, list[dict], float]:
    """The session and its feedback; returns the venture, the session, the turns and the seconds the feedback took."""
    v, ids = build(case)
    p = case["practice"]
    first = ids[case["turns"][0][0]]
    r = actions.start_practice(v, coach, first, p["character"], p["scenario"],
                               Difficulty(p.get("difficulty", Difficulty.REALISTIC.value)),
                               assumption_id=p.get("assumption_id", ""))
    turns: list[dict] = []
    for by, text in case["turns"]:
        if r.wrapped_up:
            break
        start = time.perf_counter()
        try:
            reply, error = actions.practice_message(v, coach, r.id, ids[by], text), ""
        except Exception as err:  # noqa: BLE001 - a failed turn is a finding, not a crash
            reply, error = None, f"{type(err).__name__}: {str(err)[:300]}"
        turns.append({"by": by, "text": text, "reply": reply.text if reply else "", "error": error,
                      "seconds": round(time.perf_counter() - start, 1), "wrapped_up": r.wrapped_up})
    start = time.perf_counter()
    actions.end_practice(v, coach, r.id, first)
    return v, r, turns, round(time.perf_counter() - start, 1)


def _found(pattern: re.Pattern, turns: list[dict]) -> list[str]:
    return [m.group(0) for t in turns if (m := pattern.search(t["reply"]))]


def checks(case: dict, v: Venture, r: Rehearsal, turns: list[dict]) -> list[dict]:
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append({"check": name, "ok": bool(ok), "detail": detail})

    expect = case.get("expect", {})
    limit = int(expect.get("max_words", WORD_LIMIT))
    for i, t in enumerate(turns, 1):
        if t["error"]:
            add(f"turn {i}: the character replied", False, t["error"])
            continue
        words, questions = len(t["reply"].split()), t["reply"].count("?")
        add(f"turn {i}: under {limit} words", words <= limit, f"{words} words")
        add(f"turn {i}: at most 2 questions", questions <= 2, f"{questions} question marks")
        add(f"turn {i}: stays in role (never 'as an AI')", not AI_BREAK.search(t["reply"]))
    said = " ".join([r.messages[0].text] + [t["reply"] for t in turns]).lower()
    for word in expect.get("never_says", []):
        add(f"never says \"{word}\"", word.lower() not in said)
    before = expect.get("never_says_before")
    if before:
        early = " ".join([r.messages[0].text] + [t["reply"] for t in turns[:before["turn"] - 1]]).lower()
        hits = [w for w in before["words"] if w.lower() in early]
        add(f"knows nothing about the idea before turn {before['turn']}", not hits, ", ".join(hits))
    if expect.get("no_commitment"):
        hits = _found(COMMITMENT, turns)
        add("promises nothing (no \"sign me up\")", not hits, "; ".join(hits))
    for gap in expect.get("names_gap_after", []):
        reply = turns[gap["turn"] - 1]["reply"] if len(turns) >= gap["turn"] else ""
        ok = any(re.search(rf"(?<![\w.]){re.escape(w)}", reply, re.I) for w in gap["words"])
        add(f"names the gap with the records after turn {gap['turn']}", ok, reply[:200])
    if "first_reply_mentions" in expect:
        reply = turns[0]["reply"].lower() if turns else ""
        add("says the pitch ran over in its first reply", any(w in reply for w in expect["first_reply_mentions"]),
            reply[:200])
    if expect.get("no_coaching"):
        hits = _found(COACHING, turns)
        add("never coaches or praises during the session", not hits, "; ".join(hits))
    if expect.get("no_score_talk"):
        hits = _found(SCORE_TALK, turns)
        add("announces no score, prize or decision", not hits, "; ".join(hits))
    if expect.get("no_rudeness"):
        hits = _found(RUDE, turns)
        add("tough, never rude", not hits, "; ".join(hits))
    if "wraps_up_within" in expect:
        n = expect["wraps_up_within"]
        at = next((i for i, t in enumerate(turns, 1) if t["wrapped_up"]), 0)
        add(f"closes the session within {n} team messages", 0 < at <= n, f"closed after {at}" if at else "never closed")
    fb, s = r.feedback, practice.spec(r.character)
    add("the feedback scores every rubric dimension", set(fb.scores) == {d.id for d in s.rubric},
        ", ".join(sorted(fb.scores)))
    if "feedback_fixes_mention" in expect:
        text = " ".join(fb.fixes).lower()
        hits = [w for w in expect["feedback_fixes_mention"] if w in text]
        add("the fixes name the main mistake", bool(hits), ", ".join(hits) or " / ".join(fb.fixes)[:200])
    for number in expect.get("unsupported_mention", []):
        add(f"the feedback lists the unsupported claim with {number}",
            any(re.search(rf"(?<!\d){re.escape(number)}(?!\d)", c) for c in fb.unsupported_claims))
    if expect.get("problems_listed"):
        add("the feedback lists the weak spots", bool(fb.problems), f"{len(fb.problems)} listed")
    if expect.get("checks_listed"):
        add("the feedback lists what to check with real customers", bool(fb.checks), f"{len(fb.checks)} listed")
    if "delivery_at_most" in expect:
        score = fb.scores.get("delivery", 0)
        add(f"delivery scored at most {expect['delivery_at_most']} (the pitch ran over)",
            0 < score <= expect["delivery_at_most"], f"delivery {score}")
    return out


def feedback_text(s: practice.CharacterSpec, fb: RehearsalFeedback) -> str:
    def block(title: str, items: list[str]) -> list[str]:
        return [f"{title}:", *(f"- {x}" for x in items)] if items else []

    lines = [f"Overall {fb.overall:.1f} of 5. {fb.verdict}",
             "Scores: " + "; ".join(f"{d.title} {fb.scores[d.id]}" for d in s.rubric if d.id in fb.scores),
             *block("What worked", fb.strengths), *block("Fix these", fb.fixes),
             *block("Toughest questions", fb.tough_questions), *block("Weak spots", fb.problems),
             *block("Worth checking with real customers (the customer is made up: check these before relying on "
                    "them)", fb.checks),
             *block("Claims the records don't support", fb.unsupported_claims)]
    return "\n".join(lines)


def judge(client, case: dict, v: Venture, r: Rehearsal) -> dict:
    s = practice.spec(r.character)
    prompt = JUDGE.format(character=practice.character_label(r), scenario=practice.scenario_of(r).title,
                          difficulty=r.difficulty.value, good_character=case["good_character"],
                          good_feedback=case["good_feedback"], view=access.character_view(v, r),
                          transcript=practice.transcript(v, r), feedback=feedback_text(s, r.feedback))
    try:
        data = client.chat_json("You are an experienced AIN Center EIR reviewing an AI practice partner. Strict JSON "
                                "only.", prompt)
        scores = {d: min(5, max(1, int((data.get("scores") or {})[d]))) for d in DIMENSIONS}
    except Exception as err:  # noqa: BLE001 - keep the other cases going
        return {"error": f"{type(err).__name__}: {str(err)[:200]}"}
    return {"scores": scores, "mean": round(sum(scores.values()) / len(scores), 2),
            "reasons": data.get("reasons") or {}, "fix": str(data.get("fix") or "")}


def summary(results: list[dict], model: str, started: str) -> str:
    lines = [f"# Practice evaluation run {started} · {model}", "",
             "Fictional practice cases (eval/practice_cases/). Checks need no judgment; scores (1–5) come from an AI "
             "judge and can be overruled by the team.", "",
             "| Case | Checks passed | " + " | ".join(d.replace("_", " ") for d in DIMENSIONS) + " | Mean |",
             "|---|---|" + "---|" * len(DIMENSIONS) + "---|"]
    means = {d: [] for d in DIMENSIONS}
    for r in results:
        scores = r["judge"].get("scores", {})
        for d in DIMENSIONS:
            if d in scores:
                means[d].append(scores[d])
        lines.append(f"| {r['case']} | {sum(c['ok'] for c in r['checks'])}/{len(r['checks'])} | "
                     + " | ".join(str(scores.get(d, "–")) for d in DIMENSIONS) + f" | {r['judge'].get('mean', '–')} |")
    avg = [f"{sum(x) / len(x):.1f}" if x else "–" for x in means.values()]
    total = sum(sum(c["ok"] for c in r["checks"]) for r in results)
    lines.append(f"| **All** | **{total}/{sum(len(r['checks']) for r in results)}** | "
                 + " | ".join(f"**{a}**" for a in avg) + " | |")
    failed = [f"- {r['case']}: {c['check']}" + (f" ({c['detail']})" if c["detail"] else "")
              for r in results for c in r["checks"] if not c["ok"]]
    lines += ["", "## Failed checks", *(failed or ["- none"]), "", "## The judge's main improvement per case"]
    lines += [f"- {r['case']}: {r['judge'].get('fix') or r['judge'].get('error', '–')}" for r in results]
    secs = [t["seconds"] for r in results for t in r["turns"]]
    if secs:
        lines += ["", f"Character reply time: {sum(secs) / len(secs):.1f} s on average, {max(secs):.1f} s at most."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", default="", help="comma-separated case id prefixes, e.g. p01,p03")
    parser.add_argument("--no-judge", action="store_true", help="checks only, no AI scores")
    parser.add_argument("--scripted", action="store_true", help="the characters without AI (tests the harness only)")
    parser.add_argument("--out", default="", help="results folder (default: eval/results/<date>_<time>_practice)")
    args = parser.parse_args(argv)
    if args.scripted:
        coach = ScriptedCoach()
    else:
        from smoke_llm import settings
        coach = make_coach(settings())
        if not hasattr(coach, "client"):
            print("No model configured: fill in ~/.streamlit/secrets.toml, or use --scripted.")
            return 2
    started = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = Path(args.out) if args.out else RESULTS / (datetime.now().strftime("%Y-%m-%d_%H%M") + "_practice")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for case in load_cases(args.cases):
        print(f"{case['id']} …", end=" ", flush=True)
        v, r, turns, feedback_seconds = replay(case, coach)
        result = {"case": case["id"], "model": coach.label, "character": r.character, "scenario": r.scenario,
                  "persona": r.persona, "opening": r.messages[0].text, "turns": turns,
                  "feedback": feedback_text(practice.spec(r.character), r.feedback),
                  "feedback_seconds": feedback_seconds,
                  "checks": checks(case, v, r, turns),
                  "judge": {} if args.no_judge or args.scripted else judge(coach.client, case, v, r)}
        (out / f"{case['id']}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)
        print(f"{sum(c['ok'] for c in result['checks'])}/{len(result['checks'])} checks"
              + (f", mean {result['judge']['mean']}" if result["judge"].get("mean") else ""))
    (out / "summary.md").write_text(summary(results, coach.label, started), encoding="utf-8")
    print(f"\nResults: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
