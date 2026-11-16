"""Provider-agnostic chat client, with tool calling for the lead mentor.

Configuration (environment variables or .streamlit/secrets.toml, read by the app):
  LLM_PROVIDER = "openai" | "anthropic"     LLM_API_KEY = "..."
  LLM_MODEL    = optional override           LLM_BASE_URL = optional OpenAI-compatible endpoint
  LLM_TOOLS    = "auto" (default) | "native" | "json"

`run_tools()` lets the model call actions (ToolSpec) and returns its final text.
- **Native mode:** with an OpenAI-compatible endpoint it uses native function calling.
- **JSON mode:** used when the endpoint rejects tools, when LLM_TOOLS = "json", or with Anthropic in this version.
  The model ends its reply with a fenced `actions` block instead.

Both modes go through the same handler, so the validation rules never depend on the mode.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-5.6-luna"}
MAX_TOKENS = 1200
# A sentence in which the model narrates what it is about to do ("Let me record the claims first."), not a request
# to the team ("Let me know which one you pick.")
NARRATION = re.compile(r"^(?:(?:first|now|ok|okay|so),?\s+)?(?:let me|let's|i'll|i will|i'm going to|before i)\s+"
                       r"(?:first\s+|quickly\s+)?(?:record|capture|log|note|update|set|add|save|read|open|check|look|get|"
                       r"put|write|track|start|reflect|go through|take|make sure|respond)\b[^\n]{0,160}$",
                       re.IGNORECASE)


def strip_narration(text: str) -> str:
    """Drop narration statements ("Let me record that first.") from a reply; questions and lists are kept. A reply that
    is nothing but narration stays as it is."""
    out = []
    for paragraph in (p for p in text.split("\n\n") if p.strip()):
        if paragraph.lstrip().startswith(("-", "*", "1.", "|")):  # lists and tables are content
            out.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        kept = [s for s in sentences if s.endswith("?") or not NARRATION.match(s)]
        if kept:
            out.append(" ".join(kept) if len(kept) < len(sentences) else paragraph)
    return "\n\n".join(out) or text


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model: str = ""
    base_url: str | None = None
    tools: str = "auto"  # auto | native | json

    @property
    def model_name(self) -> str:
        return self.model or DEFAULT_MODELS.get(self.provider, "")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema of an object


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)
    error: str = ""  # set when the model's arguments were not a JSON object


@dataclass
class ToolRun:
    text: str
    calls: list[tuple[ToolCall, str]] = field(default_factory=list)  # (call, result given back to the model)
    mode: str = "native"


ACTIONS_BLOCK = re.compile(r"```actions\s*(.*?)```", re.S)
JSON_ACTIONS = """

ACTIONS: to use an action, end your reply with one fenced block (the team never sees it):
```actions
[{{"tool": "<name>", "args": {{...}}}}]
```
Write [] when you take no action. Available actions and their arguments:
{catalog}"""


class LLMClient:
    def __init__(self, cfg: LLMConfig, sdk=None):
        """`sdk` replaces the provider SDK client (tests)."""
        self.cfg = cfg
        # GPT-5.6 Luna's Chat Completions endpoint supports function tools only with reasoning disabled.
        # Use its completion-token parameter from the first request; other endpoints retain the probe below.
        luna_chat = cfg.provider == "openai" and cfg.model_name == "gpt-5.6-luna"
        self._tokens_param = "max_completion_tokens" if luna_chat else "max_tokens"
        self._reasoning_effort = "none" if luna_chat else None
        if cfg.tools in ("native", "json"):
            self._tool_mode = cfg.tools
        else:
            self._tool_mode = "json" if cfg.provider == "anthropic" else "auto"
        if sdk is not None:
            self._client = sdk
        elif cfg.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=cfg.api_key)
        elif cfg.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        else:
            raise ValueError(f"Unknown LLM provider: {cfg.provider}")

    @property
    def tool_mode(self) -> str:
        """auto (not probed yet) | native | json."""
        return self._tool_mode

    # ---- plain chat ----
    def chat(self, system: str, messages: list[dict], max_tokens: int = MAX_TOKENS) -> str:
        """messages: [{"role": "user" | "assistant", "content": str}], alternating roles."""
        if self.cfg.provider == "anthropic":
            r = self._client.messages.create(model=self.cfg.model_name, system=system,
                                             messages=messages, max_tokens=max_tokens)
            return "".join(b.text for b in r.content if b.type == "text")
        r = self._create(messages=[{"role": "system", "content": system}, *messages], max_tokens=max_tokens)
        return r.choices[0].message.content or ""

    def chat_json(self, system: str, prompt: str) -> dict:
        """Ask for one JSON object; returns {} if the answer can't be parsed."""
        return parse_json_object(self.chat(system, [{"role": "user", "content": prompt}], max_tokens=1500))

    # ---- tools ----
    def run_tools(self, system: str, messages: list[dict], tools: list[ToolSpec],
                  handler: Callable[[ToolCall], str], max_rounds: int = 4) -> ToolRun:
        if self.cfg.provider == "openai" and self._tool_mode in ("auto", "native"):
            try:
                run = self._run_native(system, messages, tools, handler, max_rounds)
            except Exception as err:  # noqa: BLE001 - re-raised unless the endpoint rejects tools
                if self._tool_mode == "native" or not _rejects_tools(err):
                    raise
                self._tool_mode = "json"  # this endpoint has no function calling: use the actions block from now on
            else:
                self._tool_mode = "native"
                return run
        return self._run_json(system, messages, tools, handler)

    def _create(self, **kwargs):
        """chat.completions.create; switches to max_completion_tokens when the model requires it."""
        tokens = kwargs.pop("max_tokens", None)
        if tokens is not None:
            kwargs[self._tokens_param] = tokens
        if self._reasoning_effort is not None:
            kwargs["reasoning_effort"] = self._reasoning_effort
        try:
            return self._client.chat.completions.create(model=self.cfg.model_name, **kwargs)
        except Exception as err:  # noqa: BLE001
            if tokens is None or self._tokens_param != "max_tokens" or "max_completion_tokens" not in str(err):
                raise
            self._tokens_param = "max_completion_tokens"
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            return self._client.chat.completions.create(model=self.cfg.model_name, **kwargs)

    def _run_native(self, system, messages, tools, handler, max_rounds) -> ToolRun:
        """Models often write part of their reply together with their tool calls and the rest (or nothing) after the
        results: the reply is every round's text, in order, without repeats. With no text at all, the model is asked
        once more."""
        specs = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                   "parameters": t.parameters}} for t in tools]
        msgs: list[dict] = [{"role": "system", "content": system}, *messages]
        calls: list[tuple[ToolCall, str]] = []
        texts: list[str] = []
        for _ in range(max_rounds):
            m = self._create(messages=msgs, tools=specs, tool_choice="auto", max_tokens=MAX_TOKENS).choices[0].message
            if (m.content or "").strip() and m.content.strip() not in texts:
                texts.append(m.content.strip())
            if not m.tool_calls:
                break
            ids = [tc.id or f"call_{len(calls) + i}" for i, tc in enumerate(m.tool_calls)]
            msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for cid, tc in zip(ids, m.tool_calls)]})
            for cid, tc in zip(ids, m.tool_calls):
                call = _parse_call(cid, tc.function.name, tc.function.arguments)
                result = f"ERROR: {call.error}" if call.error else handler(call)
                calls.append((call, result))
                msgs.append({"role": "tool", "tool_call_id": cid, "content": result})
        else:  # the round limit: the model must answer in text now
            m = self._create(messages=msgs, tools=specs, tool_choice="none", max_tokens=MAX_TOKENS).choices[0].message
            if (m.content or "").strip() and m.content.strip() not in texts:
                texts.append(m.content.strip())
        if not texts:
            msgs.append({"role": "user", "content": "(note) Now reply to the team in a few sentences."})
            m = self._create(messages=msgs, tools=specs, tool_choice="none", max_tokens=MAX_TOKENS).choices[0].message
            texts.append((m.content or "").strip())
        return ToolRun(strip_narration("\n\n".join(texts)), calls, "native")

    def _run_json(self, system, messages, tools, handler) -> ToolRun:
        catalog = "\n".join(f"- {t.name}: {t.description} Arguments: {json.dumps(t.parameters.get('properties', {}))}"
                            for t in tools)
        visible, actions = split_actions(self.chat(system + JSON_ACTIONS.format(catalog=catalog), messages))
        calls: list[tuple[ToolCall, str]] = []
        for i, action in enumerate(actions):
            name = str(action.get("tool", "")) if isinstance(action, dict) else ""
            args = action.get("args") if isinstance(action, dict) else None
            call = ToolCall(f"json_{i}", name, args if isinstance(args, dict) else {},
                            "" if isinstance(args, dict) else "the arguments must be a JSON object")
            calls.append((call, f"ERROR: {call.error}" if call.error else handler(call)))
        return ToolRun(visible, calls, "json")


def _parse_call(call_id: str, name: str, arguments: str | None) -> ToolCall:
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as err:
        return ToolCall(call_id, name, {}, f"the arguments were not valid JSON ({err.msg})")
    if not isinstance(args, dict):
        return ToolCall(call_id, name, {}, "the arguments must be a JSON object")
    return ToolCall(call_id, name, args)


def _rejects_tools(err: Exception) -> bool:
    """The endpoint refused the request because of the tools parameter (no function calling)."""
    return getattr(err, "status_code", None) in (400, 404, 422) and bool(re.search(r"tool|function", str(err), re.I))


def split_actions(text: str) -> tuple[str, list]:
    """JSON mode: remove the ```actions block from a reply and parse it."""
    m = ACTIONS_BLOCK.search(text)
    if not m:
        return text.strip(), []
    try:
        actions = json.loads(m.group(1))
    except json.JSONDecodeError:
        actions = []
    return (text[:m.start()] + text[m.end():]).strip(), actions if isinstance(actions, list) else []


def parse_json_object(text: str) -> dict:
    """The first JSON object in a reply (code fences allowed); {} if none parses."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
        start = text.find("{", start + 1)
    return {}
