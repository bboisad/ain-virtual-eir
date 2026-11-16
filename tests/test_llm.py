"""The LLM client's tool loop with a fake OpenAI SDK (no network): native calls, bad arguments, the round limit,
falling back to an actions block when the endpoint rejects tools, and the max_completion_tokens switch."""
from types import SimpleNamespace as NS

from eir.llm import LLMClient, LLMConfig, ToolSpec, parse_json_object, split_actions

TOOLS = [ToolSpec("add_task", "Add a task", {"type": "object", "properties": {"text": {"type": "string"}},
                                              "required": ["text"]})]


def reply(content="", tool_calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


def call(cid, name, arguments):
    return NS(id=cid, function=NS(name=name, arguments=arguments))


class FakeSDK:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Rejected(Exception):
    status_code = 400


def client(sdk, tools="auto"):
    return LLMClient(LLMConfig("openai", "key", "model-x", None, tools), sdk=sdk)


def test_native_loop_runs_valid_calls_and_returns_errors_for_bad_arguments():
    sdk = FakeSDK(reply(tool_calls=[call("a", "add_task", '{"text": "Call Res Life"}'),
                                    call("b", "add_task", "{not json")]),
                  reply("Done. I added a task."))
    seen = []
    run = client(sdk).run_tools("system", [{"role": "user", "content": "[m1] Alice: hi"}], TOOLS,
                                lambda c: seen.append(c.args) or "ok")
    assert run.text == "Done. I added a task." and run.mode == "native"
    assert seen == [{"text": "Call Res Life"}]  # the malformed call never reaches the handler
    assert [r for _, r in run.calls] == ["ok", "ERROR: the arguments were not valid JSON (Expecting property name "
                                               "enclosed in double quotes)"]
    tool_messages = [m for m in sdk.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["a", "b"]  # results go back to the model


def test_after_the_round_limit_the_model_must_answer_in_text():
    looping = [reply(tool_calls=[call(f"c{i}", "add_task", '{"text": "x"}')]) for i in range(2)]
    sdk = FakeSDK(*looping, reply("Final answer"))
    run = client(sdk).run_tools("system", [], TOOLS, lambda c: "ok", max_rounds=2)
    assert run.text == "Final answer" and sdk.calls[-1]["tool_choice"] == "none"


def test_a_reply_written_with_the_tool_calls_is_kept_when_the_last_message_is_empty():
    sdk = FakeSDK(reply("Recorded: 4 of 5 want it free.", tool_calls=[call("a", "add_task", '{"text": "x"}')]),
                  reply(""))
    run = client(sdk).run_tools("system", [], TOOLS, lambda c: "ok")
    assert run.text == "Recorded: 4 of 5 want it free." and len(sdk.calls) == 2


def test_a_reply_split_around_the_tool_calls_is_kept_whole_without_repeats():
    sdk = FakeSDK(reply("The consultant's key points: free is the competitor.",
                        tool_calls=[call("a", "add_task", '{"text": "x"}')]),
                  reply("The consultant's key points: free is the competitor.",
                        tool_calls=[call("b", "add_task", '{"text": "y"}')]),
                  reply("When can you run the walk?"))
    run = client(sdk).run_tools("system", [], TOOLS, lambda c: "ok")
    assert run.text == "The consultant's key points: free is the competitor.\n\nWhen can you run the walk?"


def test_a_line_narrating_the_actions_is_not_part_of_the_reply():
    sdk = FakeSDK(reply("Let me record the key claims from the deck first.",
                        tool_calls=[call("a", "add_task", '{"text": "x"}')]),
                  reply("Alice, slide 3 says everyone loved it. How many did you ask?"))
    run = client(sdk).run_tools("system", [], TOOLS, lambda c: "ok")
    assert run.text == "Alice, slide 3 says everyone loved it. How many did you ask?"
    sdk = FakeSDK(reply("Let me know which slide matters most to you."))  # a reply of its own is kept
    assert client(sdk).run_tools("system", [], TOOLS, lambda c: "ok").text.startswith("Let me know")


def test_narration_inside_a_paragraph_is_dropped_too():
    from eir.llm import strip_narration
    text = "Priya, \"every hospital\" is a big leap. Let me capture the core belief and set our focus.\n\nWho buys it?"
    assert strip_narration(text) == "Priya, \"every hospital\" is a big leap.\n\nWho buys it?"
    later = "A consultant can help.\n\nLet me open that consultation now, framing both questions.\n\nWho pays?"
    assert strip_narration(later) == "A consultant can help.\n\nWho pays?"
    assert strip_narration("I'll record that.") == "I'll record that."  # nothing else to say: kept
    assert strip_narration("Let me be direct: nobody has paid yet.") == "Let me be direct: nobody has paid yet."
    assert strip_narration("Let me check: did any of them pay?") == "Let me check: did any of them pay?"  # a question


def test_with_no_text_at_all_the_model_is_asked_to_reply():
    sdk = FakeSDK(reply(tool_calls=[call("a", "add_task", '{"text": "x"}')]), reply(""), reply("Here is what I did."))
    run = client(sdk).run_tools("system", [], TOOLS, lambda c: "ok")
    assert run.text == "Here is what I did." and sdk.calls[-1]["tool_choice"] == "none"
    assert sdk.calls[-1]["messages"][-1]["content"].startswith("(note) Now reply")


def test_an_endpoint_without_tools_falls_back_to_the_actions_block():
    sdk = FakeSDK(Rejected("Error code: 400 - 'tools' is not supported for this model"),
                  reply('Noted.\n```actions\n[{"tool": "add_task", "args": {"text": "Call Res Life"}}]\n```'),
                  reply("Second turn.\n```actions\n[]\n```"))
    c = client(sdk)
    seen = []
    run = c.run_tools("system", [], TOOLS, lambda call: seen.append(call.args) or "ok")
    assert run.mode == "json" and run.text == "Noted." and seen == [{"text": "Call Res Life"}]
    assert "ACTIONS:" in sdk.calls[1]["messages"][0]["content"] and "tools" not in sdk.calls[1]
    assert c.tool_mode == "json"
    assert c.run_tools("system", [], TOOLS, lambda call: "ok").text == "Second turn."
    assert "tools" not in sdk.calls[2]  # no second probe


def test_other_errors_are_not_mistaken_for_missing_tool_support():
    sdk = FakeSDK(RuntimeError("connection reset"))
    try:
        client(sdk).run_tools("system", [], TOOLS, lambda c: "ok")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the connection error to propagate")


def test_max_tokens_switches_to_max_completion_tokens_when_the_model_requires_it():
    sdk = FakeSDK(Exception("Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."),
                  reply("OK"), reply("Again"))
    c = client(sdk)
    assert c.chat("system", [{"role": "user", "content": "hi"}]) == "OK"
    assert "max_completion_tokens" in sdk.calls[1] and "max_tokens" not in sdk.calls[1]
    c.chat("system", [{"role": "user", "content": "hi"}])
    assert "max_completion_tokens" in sdk.calls[2]


def test_luna_uses_compatible_parameters_for_chat_and_native_tool_round_trips():
    sdk = FakeSDK(reply("OK"),
                  reply(tool_calls=[call("a", "add_task", '{"text": "Interview five movers"}')]),
                  reply("The interviews are on your action plan."))
    c = LLMClient(LLMConfig("openai", "key"), sdk=sdk)
    assert c.chat("system", [{"role": "user", "content": "hi"}], max_tokens=300) == "OK"
    seen = []
    run = c.run_tools("system", [{"role": "user", "content": "Add an interview task"}], TOOLS,
                      lambda tool: seen.append(tool.args) or "saved")
    assert run.mode == "native" and seen == [{"text": "Interview five movers"}]
    assert run.text == "The interviews are on your action plan."
    assert sdk.calls[0]["max_completion_tokens"] == 300
    for request in sdk.calls:
        assert request["model"] == "gpt-5.6-luna"
        assert request["reasoning_effort"] == "none"
        assert "max_completion_tokens" in request and "max_tokens" not in request


def test_other_openai_compatible_models_keep_their_existing_parameters():
    sdk = FakeSDK(reply("OK"))
    c = LLMClient(LLMConfig("openai", "key", "databricks-claude-sonnet-4-6"), sdk=sdk)
    assert c.chat("system", [{"role": "user", "content": "hi"}]) == "OK"
    assert "reasoning_effort" not in sdk.calls[0]
    assert "max_tokens" in sdk.calls[0]


def test_json_helpers():
    assert parse_json_object('Sure:\n```json\n{"rung": 3, "why": {"a": 1}}\n```') == {"rung": 3, "why": {"a": 1}}
    assert parse_json_object("no json here") == {}
    assert split_actions("Hi\n```actions\nnot json\n```") == ("Hi", [])
