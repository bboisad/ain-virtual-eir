"""Replay the coaching cases (eval/cases/) through the lead mentor and score every reply. Fictional data only.

Run from virtual_eir/:  python eval/run_eval.py [--cases case07,case08] [--no-judge] [--scripted]

For each case: a fresh in-memory venture, the student's turns sent one by one (a later session is moved one day back,
so the mentor's "last time" memory is exercised), then
- checks that need no judgment: reply length, at most two questions, no internal ids, no narration, never a "step
  complete" claim; per case: hands off to a human or not, records no evidence above the case's rung, brings in only a
  fitting consultant, keeps an Optimize team in Optimize;
- an AI judge (the same model) scores six dimensions from 1 to 5 against "what a good EIR does here", taken from
  Roberto's examples. The team can overrule any score; keep notes in eval/results/NOTES.md.
Results: eval/results/<date>_<time>/<case>.json and summary.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from eir import actions, changes, consult, teams  # noqa: E402
from eir.access import Account  # noqa: E402
from eir.coach import make_coach  # noqa: E402
from eir.coach.scripted import ScriptedCoach  # noqa: E402
from eir.filestore import MemoryFileStore  # noqa: E402
from eir.llm import NARRATION  # noqa: E402
from eir.models import LeadMode, Rung, Venture, VentureType  # noqa: E402
from eir.repository import InMemoryRepository  # noqa: E402

CASES = ROOT / "eval" / "cases"
RESULTS = ROOT / "eval" / "results"
WORD_LIMIT = 180
DIMENSIONS = ("challenge", "evidence", "focus", "handoff", "respect", "next_step")
IDS = re.compile(r"\b(?:S-[0-9a-f]{6,}|S\d{1,2}|X-[A-Za-z0-9-]+|K-[0-9a-f]{6}|F-[A-Za-z0-9]+)\b")
STEP_CLAIM = re.compile(r"\b(?:step|deliverable|module) (?:is |has been )?(?:complete|done|finished)\b|"
                        r"\byou (?:can |may )?(?:now )?move on to (?:M\d|the next module)\b", re.IGNORECASE)
JUDGE = """You review how a virtual mentor (an AI EIR) coached a student venture team, against how a good human EIR at
the AIN Center (University of Rochester) would coach.

WHAT A GOOD EIR DOES HERE:
{good}

THE CONVERSATION (with the records the mentor updated):
{transcript}

Human handoff requested by the mentor: {handoff}

Score each dimension from 1 (poor) to 5 (excellent):
- challenge: questions the claim instead of accepting it, without destroying the idea
- evidence: grades evidence correctly (believed / desk research / said / did / paid) and records nothing stronger than
  the team reported
- focus: one or two sharp questions in a sensible order, concise, no lecture
- handoff: sends to a human exactly what needs a human (team, equity, CEO, valuation, term sheets, IP strategy, FDA
  pathway), and nothing else
- respect: truthful and respectful, no flattery, does not judge the idea itself
- next_step: leaves the team with a specific next action or test
Return one JSON object: {{"scores": {{"challenge": n, "evidence": n, "focus": n, "handoff": n, "respect": n,
"next_step": n}}, "reasons": {{"<dimension>": "<one sentence>"}}, "fix": "<the single most important improvement>"}}"""


def load_cases(only: str = "") -> list[dict]:
    wanted = [w.strip() for w in only.split(",") if w.strip()]
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if not wanted or any(c["id"].startswith(w) for w in wanted)]


def build(case: dict) -> tuple[Venture, dict[str, str]]:
    """A fresh venture with the case's team; returns it and first name -> member id."""
    spec = case["venture"]
    accounts = [Account(f"eval-{i}", name) for i, name in enumerate(spec["members"])]
    v = teams.create_workspace(InMemoryRepository([]), accounts[0], spec["name"], spec.get("description", ""),
                               venture_type=VentureType(spec.get("type", VentureType.MARKET.value)),
                               ip_sensitive=bool(spec.get("ip_sensitive")),
                               lead_mode=LeadMode(spec.get("lead_mode", LeadMode.LAUNCH.value)))
    for account in accounts[1:]:
        teams.join_venture(v, account)
    return v, {m.first_name: m.id for m in v.members}


def _yesterday(v: Venture) -> None:
    for m in v.conversation:
        m.created_at = (datetime.fromisoformat(m.created_at) - timedelta(days=1)).isoformat(timespec="seconds")


def replay(case: dict, coach) -> tuple[Venture, list[dict]]:
    v, ids = build(case)
    store, turns = MemoryFileStore(), []
    for number, session in enumerate(case["sessions"], 1):
        if number > 1:
            _yesterday(v)
        for by, text in session:
            start = time.perf_counter()
            try:
                reply, error = actions.mentor_message(v, coach, ids[by], text, files=store), ""
            except Exception as err:  # noqa: BLE001 - a failed turn is a finding, not a crash
                reply, error = None, f"{type(err).__name__}: {str(err)[:300]}"
            c = v.consultation(reply.consultation_id) if reply and reply.consultation_id else None
            turns.append({
                "session": number, "by": by, "text": text, "reply": reply.text if reply else "", "error": error,
                "seconds": round(time.perf_counter() - start, 1),
                "updates": [ch.summary for g in (reply.change_groups if reply else []) for ch in changes.changes_in(v, g)],
                "consultation": consult.name_of(c.consultant) if c else "",
                "suggested_mode": reply.suggested_mode.value if reply and reply.suggested_mode else "",
            })
    return v, turns


def recorded_rung(v: Venture) -> int:
    """The strongest evidence the mentor recorded in this run (the venture started empty)."""
    rungs = [i.rung for h in v.hypotheses for i in h.evidence_items] + [a.rung for a in v.answers.values()]
    rungs += [e.rung for e in v.canvas.values()] + [g.rung for g in v.lenses.values()]
    return int(max(rungs, default=Rung.NONE))


def checks(case: dict, v: Venture, turns: list[dict]) -> list[dict]:
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append({"check": name, "ok": bool(ok), "detail": detail})

    for i, t in enumerate(turns, 1):
        if t["error"]:
            add(f"turn {i}: the mentor replied", False, t["error"])
            continue
        words, questions, ids = len(t["reply"].split()), t["reply"].count("?"), IDS.findall(t["reply"])
        add(f"turn {i}: under {WORD_LIMIT} words", words <= WORD_LIMIT, f"{words} words")
        add(f"turn {i}: at most 2 questions", questions <= 2, f"{questions} question marks")
        add(f"turn {i}: no internal ids", not ids, ", ".join(sorted(set(ids))))
        first = re.split(r"(?<=[.!?])\s+", t["reply"].strip())
        add(f"turn {i}: no narration", not any(NARRATION.match(s) for s in first[:3]))
        add(f"turn {i}: never says a step is complete", not STEP_CLAIM.search(t["reply"]))
    expect = case.get("expect", {})
    if "handoff" in expect:
        name = "hands the decision to a human" if expect["handoff"] else "no human handoff needed"
        add(name, bool(v.handoff) == bool(expect["handoff"]), v.handoff or "none")
    if "max_rung" in expect:
        top = recorded_rung(v)
        add(f"records no evidence above rung {expect['max_rung']}", top <= expect["max_rung"], f"highest: {top}")
    if "consultants" in expect:
        opened = [c.consultant for c in v.consultations]
        add("brings in only a fitting consultant", all(c in expect["consultants"] for c in opened),
            ", ".join(opened) or "none opened")
    if "no_switch_to" in expect:
        add(f"does not suggest the {expect['no_switch_to']} mentor",
            not any(t["suggested_mode"] == expect["no_switch_to"] for t in turns))
    return out


def transcript(turns: list[dict]) -> str:
    rows = []
    for t in turns:
        row = f"[session {t['session']}] {t['by']}: {t['text']}\nMENTOR: {t['reply'] or '(no reply: ' + t['error'] + ')'}"
        if t["updates"]:
            row += "\n(record updates: " + "; ".join(t["updates"]) + ")"
        if t["consultation"]:
            row += f"\n(brought in the {t['consultation']} consultant)"
        rows.append(row)
    return "\n\n".join(rows)


def judge(client, case: dict, v: Venture, turns: list[dict]) -> dict:
    prompt = JUDGE.format(good=case["good_eir"], transcript=transcript(turns), handoff=v.handoff or "none")
    try:
        data = client.chat_json("You are an experienced AIN Center EIR reviewing a virtual mentor. Strict JSON only.",
                                prompt)
        scores = {d: min(5, max(1, int((data.get("scores") or {})[d]))) for d in DIMENSIONS}
    except Exception as err:  # noqa: BLE001 - keep the other cases going
        return {"error": f"{type(err).__name__}: {str(err)[:200]}"}
    return {"scores": scores, "mean": round(sum(scores.values()) / len(scores), 2),
            "reasons": data.get("reasons") or {}, "fix": str(data.get("fix") or "")}


def summary(results: list[dict], model: str, started: str) -> str:
    lines = [f"# Evaluation run {started} · {model}", "",
             "Fictional cases from Roberto's examples (eval/cases/). Checks need no judgment; scores (1–5) come from an "
             "AI judge and can be overruled by the team.", "",
             "| Case | Checks passed | " + " | ".join(d.replace("_", " ") for d in DIMENSIONS) + " | Mean |",
             "|---|---|" + "---|" * len(DIMENSIONS) + "---|"]
    means = {d: [] for d in DIMENSIONS}
    for r in results:
        passed = sum(c["ok"] for c in r["checks"])
        scores = r["judge"].get("scores", {})
        for d in DIMENSIONS:
            if d in scores:
                means[d].append(scores[d])
        cells = [str(scores.get(d, "–")) for d in DIMENSIONS]
        lines.append(f"| {r['case']} | {passed}/{len(r['checks'])} | " + " | ".join(cells)
                     + f" | {r['judge'].get('mean', '–')} |")
    avg = [f"{sum(x) / len(x):.1f}" if x else "–" for x in means.values()]
    total = sum(sum(c["ok"] for c in r["checks"]) for r in results)
    count = sum(len(r["checks"]) for r in results)
    lines.append(f"| **All** | **{total}/{count}** | " + " | ".join(f"**{a}**" for a in avg) + " | |")
    failed = [f"- {r['case']}: {c['check']}" + (f" ({c['detail']})" if c["detail"] else "")
              for r in results for c in r["checks"] if not c["ok"]]
    lines += ["", "## Failed checks", *(failed or ["- none"]), "", "## The judge's main improvement per case"]
    lines += [f"- {r['case']}: {r['judge'].get('fix') or r['judge'].get('error', '–')}" for r in results]
    secs = [t["seconds"] for r in results for t in r["turns"]]
    if secs:
        lines += ["", f"Mentor reply time: {sum(secs) / len(secs):.1f} s on average, {max(secs):.1f} s at most."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", default="", help="comma-separated case id prefixes, e.g. case07,case08")
    parser.add_argument("--no-judge", action="store_true", help="checks only, no AI scores")
    parser.add_argument("--scripted", action="store_true", help="use the scripted mentor (tests the harness only)")
    parser.add_argument("--out", default="", help="results folder (default: eval/results/<date>_<time>)")
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
    out = Path(args.out) if args.out else RESULTS / datetime.now().strftime("%Y-%m-%d_%H%M")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for case in load_cases(args.cases):
        print(f"{case['id']} …", end=" ", flush=True)
        v, turns = replay(case, coach)
        result = {"case": case["id"], "model": coach.label, "turns": turns, "checks": checks(case, v, turns),
                  "handoff": v.handoff or "",
                  "judge": {} if args.no_judge or args.scripted else judge(coach.client, case, v, turns)}
        (out / f"{case['id']}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)
        print(f"{sum(c['ok'] for c in result['checks'])}/{len(result['checks'])} checks"
              + (f", mean {result['judge']['mean']}" if result["judge"].get("mean") else ""))
    (out / "summary.md").write_text(summary(results, coach.label, started), encoding="utf-8")
    print(f"\nResults: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
