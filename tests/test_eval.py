"""The evaluation harnesses (eval/run_eval.py for the mentor, eval/run_practice_eval.py for the practice characters)
with the scripted coach: no API calls, so only the plumbing is tested."""
import importlib.util
import json
from pathlib import Path

from eir import practice
from eir.coach.scripted import ScriptedCoach
from eir.models import LeadMode

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "eval" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load("run_eval")
run_practice_eval = _load("run_practice_eval")


def test_every_case_is_fictional_and_complete():
    cases = run_eval.load_cases()
    assert len(cases) == 10 and len({c["id"] for c in cases}) == 10
    for c in cases:
        assert c["good_eir"] and c["source"] and c["sessions"] and "Fictional" in c["note"]
        members = {name.split()[0] for name in c["venture"]["members"]}
        assert all(by in members for session in c["sessions"] for by, _ in session), c["id"]


def test_a_case_is_replayed_and_checked():
    case = run_eval.load_cases("case08")[0]
    v, turns = run_eval.replay(case, ScriptedCoach())
    assert v.lead_mode == LeadMode.OPTIMIZE and [t["by"] for t in turns] == ["Omar", "Omar"]
    assert all(t["reply"] and not t["error"] for t in turns)
    names = [c["check"] for c in run_eval.checks(case, v, turns)]
    assert "turn 1: under 180 words" in names and "does not suggest the Launch mentor" in names
    assert "records no evidence above rung 5" in names


def test_later_sessions_happen_a_day_later():
    case = run_eval.load_cases("case10")[0]
    v, turns = run_eval.replay(case, ScriptedCoach())
    assert [t["session"] for t in turns] == [1, 1, 1, 2, 2]
    assert len(v.day_summaries) == 1  # the first session is summarized as "last time"


def test_the_summary_lists_failed_checks(tmp_path):
    assert run_eval.main(["--scripted", "--cases", "case07", "--out", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "case07_team_equity.json").read_text(encoding="utf-8"))
    assert result["judge"] == {} and any(not c["ok"] for c in result["checks"])  # the script cannot judge equity
    assert "hands the decision to a human" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_the_checks_catch_ids_narration_and_step_claims():
    assert run_eval.IDS.findall("Run X-fee before S1 is done; H2 is fine") == ["X-fee", "S1"]
    assert run_eval.NARRATION.match("Let me record that first.")
    assert run_eval.STEP_CLAIM.search("Great: this step is complete, you can move on to M3.")
    assert not run_eval.STEP_CLAIM.search("Press Check this step when you are ready.")


# ---- the practice characters ----
def test_every_practice_case_is_fictional_and_uses_a_known_character():
    cases = run_practice_eval.load_cases()
    assert [c["id"][:3] for c in cases] == ["p01", "p02", "p03"]
    for c in cases:
        assert c["good_character"] and c["good_feedback"] and c["turns"] and "Fictional" in c["note"]
        s = practice.spec(c["practice"]["character"])
        assert s.scenario(c["practice"]["scenario"])
        members = {name.split()[0] for name in c["venture"]["members"]}
        assert all(by in members for by, _ in c["turns"]), c["id"]


def test_a_practice_case_is_replayed_with_its_records_and_checked():
    case = run_practice_eval.load_cases("p02")[0]
    v, r, turns, _ = run_practice_eval.replay(case, ScriptedCoach())
    assert [h.statement for h in v.hypotheses][1] == "Departments will pay a 10% booking fee"
    assert r.character == "challenger" and r.feedback is not None and [t["by"] for t in turns][:2] == ["Ravi", "Ravi"]
    results = {c["check"]: c["ok"] for c in run_practice_eval.checks(case, v, r, turns)}
    assert results["names the gap with the records after turn 1"]  # the scripted challenger names numbers too
    assert results["the feedback lists the unsupported claim with 50"] and "tough, never rude" in results


def test_the_practice_summary_is_written(tmp_path):
    assert run_practice_eval.main(["--scripted", "--cases", "p01", "--out", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "p01_customer_stays_in_role.json").read_text(encoding="utf-8"))
    assert result["judge"] == {} and result["persona"] and result["feedback"].startswith("Overall")
    names = [c["check"] for c in result["checks"]]
    assert "never says \"ParkSwap\"" in names and "knows nothing about the idea before turn 3" in names
    assert "Practice evaluation run" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_the_practice_checks_catch_coaching_commitments_and_score_talk():
    assert run_practice_eval.COACHING.search("Good pitch. You should lead with the numbers.")
    assert not run_practice_eval.COACHING.search("Thank you. Who exactly is your first customer?")
    assert run_practice_eval.COMMITMENT.search("Honestly? Sign me up.")
    assert not run_practice_eval.COMMITMENT.search("Maybe? I'd have to see it.")
    assert run_practice_eval.SCORE_TALK.search("I'd give that pitch 7/10.")
    assert run_practice_eval.AI_BREAK.search("As an AI, I can't really say.")
