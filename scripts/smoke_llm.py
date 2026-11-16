"""Connection test for the configured LLM endpoint. Never prints the API key.

Reads LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL from environment variables, or from
~/.streamlit/secrets.toml and .streamlit/secrets.toml (the same names the app uses).

Run from virtual_eir/:  python scripts/smoke_llm.py
Checks the model list, a plain reply, a native tool round trip and a JSON reply, with the latency of each.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import tomllib
from pathlib import Path

NAMES = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TOOLS")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eir.llm import LLMClient, LLMConfig, ToolSpec  # noqa: E402


def settings() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (Path.home() / ".streamlit" / "secrets.toml", ROOT / ".streamlit" / "secrets.toml"):
        if path.exists():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            found.update({k: str(v) for k, v in data.items() if k in NAMES and v})
    found.update({k: os.environ[k] for k in NAMES if os.environ.get(k)})
    return found


AUTH_FAILED: list[str] = []


def timed(label: str, fn) -> bool:
    start = time.perf_counter()
    try:
        result = fn()
        print(f"[ok]   {label} ({time.perf_counter() - start:.1f}s): {result}")
        return True
    except Exception as err:  # noqa: BLE001 - report every failure and keep going
        if getattr(err, "status_code", None) in (401, 403):
            AUTH_FAILED.append(label)
        detail = re.sub(r"sk-[A-Za-z0-9_*.-]+", "[REDACTED]", str(err))
        print(f"[fail] {label} ({time.perf_counter() - start:.1f}s): {type(err).__name__}: {detail[:300]}")
        return False


def main() -> int:
    s = settings()
    missing = [n for n in ("LLM_PROVIDER", "LLM_API_KEY") if not s.get(n)]
    if missing:
        print("Missing settings: " + ", ".join(missing) + ". Fill them in ~/.streamlit/secrets.toml.")
        return 2
    if s["LLM_PROVIDER"] != "openai":
        print(f"This test covers OpenAI-compatible endpoints; LLM_PROVIDER is {s['LLM_PROVIDER']!r}.")
        return 2

    from openai import OpenAI
    client = OpenAI(api_key=s["LLM_API_KEY"], base_url=s.get("LLM_BASE_URL") or None, timeout=60)
    print(f"Endpoint: {s.get('LLM_BASE_URL') or 'api.openai.com (default)'} · key: set (not shown)")

    models: list[str] = []

    def list_models() -> str:
        models.extend(m.id for m in client.models.list())
        return f"{len(models)} models: " + ", ".join(models[:15]) + (" ..." if len(models) > 15 else "")

    timed("list models", list_models)
    model = s.get("LLM_MODEL") or (models[0] if models else "")
    if not model:
        print("No LLM_MODEL set and the endpoint did not list models: set LLM_MODEL.")
        return 2
    print(f"Model: {model}" + ("" if s.get("LLM_MODEL") else " (first listed; set LLM_MODEL to choose)"))
    llm = LLMClient(LLMConfig("openai", s["LLM_API_KEY"], model, s.get("LLM_BASE_URL") or None), sdk=client)

    def plain() -> str:
        text = llm.chat("Follow the user's instruction.",
                        [{"role": "user", "content": "Reply with the single word: OK"}])
        if text.strip() != "OK":
            raise RuntimeError(f"Expected OK, got {text[:80]!r}")
        return repr(text.strip())

    plain_ok = timed("plain reply", plain)

    tool = ToolSpec("record_note", "Record a short note for the team.",
                    {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})

    def tools() -> str:
        run = llm.run_tools("Use the requested tool, then briefly confirm.", [{"role": "user", "content":
                            "Use the record_note tool to record the note 'interview 5 movers'."}],
                            [tool], lambda call: "Note recorded.")
        if run.mode != "native" or not run.calls or not run.text.strip():
            raise RuntimeError("Native tool call and follow-up reply did not both succeed")
        call, _ = run.calls[0]
        if call.name != "record_note" or not call.args.get("text") or call.error:
            raise RuntimeError("The model did not produce a valid record_note call")
        return f"{call.name}({json.dumps(call.args)}) -> {run.text[:120]}"

    native = timed("native tool calling", tools)

    def json_mode() -> object:
        result = llm.chat_json("Return strict JSON only.", 'Return the JSON object {"ok": true} and nothing else.')
        if result != {"ok": True}:
            raise RuntimeError(f"Expected a valid JSON object with ok=true, got {result!r}")
        return result

    json_ok = timed("JSON reply", json_mode)
    if AUTH_FAILED:
        print("\nResult: the endpoint rejected the key (401/403). Fix the key first; tool support is unknown.")
        return 1
    if not (plain_ok and native and json_ok):
        print("\nResult: one or more model integration checks failed; see the failures above.")
        return 1
    print("\nResult: plain reply, native tool calling and JSON reply all work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
