"""Fictional demo ventures and their scripted conversations (eir/seed/*.json).

Each seed file: {"venture": <Venture>, "script": [<ScriptLine>, ...],
                 "consult_script": {<consultant id>: {"lines": [<ScriptLine>, ...], "summary": <ConsultationSummary>}},
                 "practice_script": {<character id>: {<scenario id>: <PracticeScript>}}}.
Files starting with "_" are not ventures: `_starters.json` (script for ventures created in the app),
`_accounts.json` (demo login accounts).
To add a demo venture: drop a new JSON file in eir/seed/ — no code changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from functools import lru_cache
from pathlib import Path

from .access import Account
from .migrate import upgrade
from .models import ConsultationSummary, RehearsalFeedback, Venture
from .serde import from_dict

SEED_DIR = Path(__file__).parent / "seed"
STARTERS = "_starters"


@dataclass
class ScriptLine:
    """One scripted exchange: a suggested founder message, the prepared answer and, for the lead mentor, the record
    updates it makes (actions such as {"name": "add_task", "args": {...}}; see eir/tools.py)."""
    id: str
    speaker: str  # member id, or "any"
    text: str
    reply: str
    tools: list[dict] = field(default_factory=list)
    propose_end: bool = False  # consultants: the reply proposes to end the consultation
    wrap_up: bool = False  # practice characters: the reply closes the session


@dataclass
class ConsultScript:
    """A consultant's prepared lines for one demo venture, and the summary it writes at the end."""
    lines: list[ScriptLine]
    summary: ConsultationSummary | None = None


@dataclass
class PracticeScript:
    """A practice character's prepared lines for one demo venture and scenario, and the feedback for them."""
    lines: list[ScriptLine]
    persona: str = ""  # target customer: who they are
    persona_profile: str = ""
    first: str = ""  # the first question, for openings that ask one ({first})
    feedback: RehearsalFeedback | None = None  # used when every team message was a prepared line


def _read(name: str) -> dict:
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _script(raw: list[dict]) -> list[ScriptLine]:
    names = {f.name for f in fields(ScriptLine)}
    return [ScriptLine(**{k: val for k, val in item.items() if k in names}) for item in raw]


def _consult_scripts(raw: dict) -> dict[str, ConsultScript]:
    return {cid: ConsultScript(_script(item.get("lines", [])),
                               from_dict(ConsultationSummary, item["summary"]) if item.get("summary") else None)
            for cid, item in raw.items()}


def _venture_files() -> list[Path]:
    return [p for p in sorted(SEED_DIR.glob("*.json")) if not p.stem.startswith("_")]


def demo_ventures() -> list[Venture]:
    """Fresh copies every call (callers mutate them), upgraded to the current data version."""
    return [upgrade(from_dict(Venture, _read(p.stem)["venture"])) for p in _venture_files()]


def demo_accounts() -> list[Account]:
    return [from_dict(Account, a) for a in _read("_accounts")["accounts"]]


@lru_cache
def scripts() -> dict[str, list[ScriptLine]]:
    """venture id -> script; key STARTERS for any venture without its own script."""
    out = {STARTERS: _script(_read(STARTERS)["script"])}
    for p in _venture_files():
        data = _read(p.stem)
        out[data["venture"]["id"]] = _script(data.get("script", []))
    return out


def script_for(venture_id: str) -> list[ScriptLine]:
    s = scripts()
    return s.get(venture_id) or s[STARTERS]


@lru_cache
def consult_scripts() -> dict[str, dict[str, ConsultScript]]:
    """venture id -> consultant id -> script ("consult_script" in the seed file)."""
    return {(data := _read(p.stem))["venture"]["id"]: _consult_scripts(data.get("consult_script", {}))
            for p in _venture_files()}


def consult_script_for(venture_id: str, consultant_id: str) -> ConsultScript | None:
    return consult_scripts().get(venture_id, {}).get(consultant_id)


def _practice_script(item: dict) -> PracticeScript:
    return PracticeScript(_script(item.get("lines", [])), item.get("persona", ""), item.get("persona_profile", ""),
                          item.get("first", ""),
                          from_dict(RehearsalFeedback, item["feedback"]) if item.get("feedback") else None)


@lru_cache
def practice_scripts() -> dict[str, dict[str, dict[str, PracticeScript]]]:
    """venture id -> character id -> scenario id -> script ("practice_script" in the seed file)."""
    return {(data := _read(p.stem))["venture"]["id"]: {
        character: {scenario: _practice_script(item) for scenario, item in scenarios.items()}
        for character, scenarios in data.get("practice_script", {}).items()} for p in _venture_files()}


def practice_script_for(venture_id: str, character_id: str, scenario_id: str) -> PracticeScript | None:
    return practice_scripts().get(venture_id, {}).get(character_id, {}).get(scenario_id)
