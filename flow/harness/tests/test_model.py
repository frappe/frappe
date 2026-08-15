import asyncio

import httpx
import pytest

from flow.events import (
	AssistantMessage,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow.model import (
	_NATIVE_PROVIDERS,
	LiteLLMModel,
	MockModel,
	ModelRequest,
	ProviderError,
	get_model,
	register_provider,
)
from flow.model.base import (
	extract_tool_call_display_metadata,
	render_tool_call_display,
	tool_call_display_ready_event,
)
from flow.model.litellm import (
	_build_tool_call,
	_openai_messages,
	_reasoning_blocks,
	_reasoning_field,
	_stop_reason,
	_usage_event,
)
from flow.model.providers.codex import CodexModel


def _chunk(delta: dict, finish_reason: str | None = None) -> dict:
	return {"choices": [{"delta": delta, "finish_reason": finish_reason}]}


def _stream(monkeypatch, chunks: list[dict]):
	async def completion(**kwargs):
		async def iterator():
			for chunk in chunks:
				yield chunk

		return iterator()

	monkeypatch.setattr("litellm.acompletion", completion)


async def _collect(gen):
	return [ev async for ev in gen]


def test_tool_call_display_metadata_is_early_and_bounded():
	partial = '{"path":"ui/App.vue","edits":[{"old":"' + ("x" * 10_000)

	assert extract_tool_call_display_metadata(partial) == {"path": "ui/App.vue"}
	assert extract_tool_call_display_metadata({"command": "x" * 1_000}) == {"command": "x" * 512}


def test_tool_call_display_waits_for_every_referenced_argument():
	template = "Searching {{ source }} for {{ query }}"

	assert render_tool_call_display(template, '{"source":"the web","query":"Flo') is None
	assert (
		render_tool_call_display(template, '{"source":"the web","query":"Flow","options":[')
		== "Searching the web for Flow"
	)
	assert render_tool_call_display("Opening page {{ page }}", '{"page":1') is None
	assert (
		render_tool_call_display("Opening page {{ page }}", '{"page":10}', complete=True) == "Opening page 10"
	)


def test_static_tool_display_is_ready_before_arguments_arrive():
	event = tool_call_display_ready_event(
		"call-1",
		"bash",
		"",
		display_template="Running command",
	)

	assert event is not None
	assert event.arguments == {}
	assert event.display == "Running command"


async def test_mock_streaming_sequence():
	events = await _collect(MockModel().run(ModelRequest(messages=[UserMessage(content="hi there")])))
	types = [e.type for e in events]
	assert types[-2:] == ["assistant_message", "usage"]
	assert all(t == "text_delta" for t in types[:-2])
	assert len(types) > 2  # streamed as several deltas

	assistant = events[-2]
	assert assistant.text == "Mock reply to: hi there"
	assert "".join(e.text for e in events[:-2]) == assistant.text


async def test_mock_non_streaming_has_no_deltas():
	events = await _collect(MockModel().run(ModelRequest(messages=[UserMessage(content="hi")], stream=False)))
	assert [e.type for e in events] == ["assistant_message", "usage"]


async def test_mock_renders_custom_tool_display_in_live_and_durable_calls():
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="web_search", arguments={"query": "Flow"})])
		]
	)
	request = ModelRequest(
		messages=[UserMessage(content="search")],
		tool_display_templates={"web_search": "Searching the web for {{ query }}"},
	)

	events = await _collect(model.run(request))

	assert events[1].display == "Searching the web for Flow"
	assert events[2].tool_calls[0].display == "Searching the web for Flow"


async def test_mock_scripted_replies_multi_turn():
	call = ToolCall(id="c1", name="bash", arguments={"command": "ls"})
	model = MockModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])

	first = await _collect(model.run(ModelRequest(messages=[UserMessage(content="go")])))
	assert [e.type for e in first] == [
		"tool_call_started",
		"tool_call_display_ready",
		"assistant_message",
		"usage",
	]
	assert first[0].id == "c1" and first[0].name == "bash"
	assert first[1].arguments == {"command": "ls"}
	assert first[2].tool_calls[0].args == {"command": "ls"}

	second = await _collect(model.run(ModelRequest(messages=[UserMessage(content="go")])))
	assert second[-2].text == "done"


async def test_litellm_cancellation_closes_active_stream(monkeypatch):
	class BlockingStream:
		def __init__(self):
			self.started = asyncio.Event()
			self.closed = asyncio.Event()

		def __aiter__(self):
			return self

		async def __anext__(self):
			self.started.set()
			await asyncio.Event().wait()

		async def aclose(self):
			self.closed.set()

	stream = BlockingStream()

	async def completion(**kwargs):
		return stream

	monkeypatch.setattr("litellm.acompletion", completion)
	cancellation = asyncio.Event()
	model = LiteLLMModel("openai/test")
	task = asyncio.create_task(
		_collect(
			model.run(
				ModelRequest(
					messages=[UserMessage(content="hi")],
					cancellation=cancellation,
				)
			)
		)
	)
	await stream.started.wait()
	cancellation.set()
	events = await asyncio.wait_for(task, timeout=1)

	assert stream.closed.is_set()
	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].stop_reason == "aborted"


async def test_litellm_disables_sdk_retries_and_owns_the_attempts(monkeypatch):
	"""One acompletion call is one provider attempt; the retry budget lives in Flow."""
	monkeypatch.setattr("flow.model.base._retry_delay_seconds", lambda error, retry_index: 0)
	seen_kwargs = {}
	attempts = 0

	async def completion(**kwargs):
		import litellm

		nonlocal attempts
		attempts += 1
		seen_kwargs.update(kwargs)
		request = httpx.Request("POST", "https://provider.test")
		response = httpx.Response(429, headers={"retry-after": "3"}, request=request)
		raise litellm.RateLimitError(
			message="rate limited",
			llm_provider="openai",
			model="test",
			response=response,
		)

	monkeypatch.setattr("litellm.acompletion", completion)
	model = LiteLLMModel("openai/test")

	with pytest.raises(ProviderError) as raised:
		await _collect(model.run(ModelRequest(messages=[UserMessage(content="hi")], stream=False)))

	assert seen_kwargs["num_retries"] == 0
	assert attempts == 3  # the shared envelope exhausted its transient budget
	assert raised.value.kind == "rate_limit"
	assert raised.value.retryable is True
	assert raised.value.status_code == 429
	assert raised.value.retry_after_seconds == 3


def test_get_model_mock():
	assert isinstance(get_model("mock"), MockModel)


def test_get_model_falls_through_to_litellm():
	model = get_model("anthropic/claude-3-5-sonnet", api_key="sk-test", api_base="https://x")
	assert isinstance(model, LiteLLMModel)
	assert model.name == "anthropic/claude-3-5-sonnet"
	assert model._api_key == "sk-test"
	assert model._api_base == "https://x"


def test_register_provider_dispatch():
	sentinel = MockModel()
	register_provider("dummy", lambda name, **kwargs: sentinel)
	try:
		assert get_model("dummy/whatever") is sentinel
	finally:
		_NATIVE_PROVIDERS.pop("dummy", None)


def test_get_model_dispatches_codex():
	model = get_model("codex/gpt-test", api_key="token")
	assert isinstance(model, CodexModel)


def test_get_model_forwards_the_refresh_hook():
	async def refresh_auth(rejected_token):
		raise AssertionError("never called here")

	model = get_model("codex/gpt-test", api_key="token", refresh_auth=refresh_auth)
	assert model._refresh_auth is refresh_auth


def test_opencode_go_routes_openai_family_to_chat_completions():
	model = get_model("opencode-go/grok-4.5", api_key="sk-go")
	assert isinstance(model, LiteLLMModel)
	assert model.name == "openai/grok-4.5"
	assert model._api_base == "https://opencode.ai/zen/go/v1"
	assert model.provider == "opencode-go"
	assert model.model == "opencode-go/grok-4.5"


def test_opencode_go_routes_anthropic_families_to_messages():
	for name, route in (
		("opencode-go/minimax-m3", "anthropic/minimax-m3"),
		("opencode-go/qwen3.7-max", "anthropic/qwen3.7-max"),
	):
		model = get_model(name, api_key="sk-go")
		assert isinstance(model, LiteLLMModel)
		assert model.name == route
		assert model._api_base == "https://opencode.ai/zen/go/v1/messages"
		assert model.model == name


def test_opencode_go_honours_api_base_override():
	def api_base(name, base):
		model = get_model(name, api_base=base)
		assert isinstance(model, LiteLLMModel)
		return model._api_base

	assert api_base("opencode-go/kimi-k3", "https://proxy.test/v1") == "https://proxy.test/v1"
	assert api_base("opencode-go/minimax-m3", "https://proxy.test/v1") == "https://proxy.test/v1/messages"
	# litellm appends /v1/messages itself when the base is not a versioned root
	assert api_base("opencode-go/minimax-m3", "https://proxy.test") == "https://proxy.test"


def test_opencode_go_rejects_bare_prefix():
	with pytest.raises(ValueError, match="opencode-go/<model-id>"):
		get_model("opencode-go")


def test_stop_reason_prefers_the_provider_signal_over_tool_presence():
	assert _stop_reason("length", has_tools=True) == "length"
	assert _stop_reason("content_filter", has_tools=True) == "error"
	# a plain stop is still upgraded, which is why has_tools exists
	assert _stop_reason("stop", has_tools=True) == "tool_use"
	assert _stop_reason(None, has_tools=True) == "tool_use"
	assert _stop_reason("tool_calls", has_tools=False) == "tool_use"


async def test_litellm_streaming_truncated_tool_call_reports_length(monkeypatch):
	_stream(
		monkeypatch,
		[
			_chunk(
				{
					"tool_calls": [
						{
							"index": 0,
							"id": "c1",
							"function": {"name": "bash", "arguments": '{"command":"ls"}'},
						}
					]
				}
			),
			_chunk({}, "length"),
		],
	)

	events = await _collect(LiteLLMModel("gpt-4").run(ModelRequest(messages=[UserMessage(content="hi")])))

	assistant = next(e for e in events if isinstance(e, AssistantMessage))
	assert assistant.tool_calls[0].id == "c1"
	assert assistant.stop_reason == "length"


async def test_litellm_emits_metadata_before_large_arguments_finish(monkeypatch):
	_stream(
		monkeypatch,
		[
			_chunk(
				{
					"tool_calls": [
						{
							"index": 0,
							"id": "c1",
							"function": {
								"name": "edit",
								"arguments": '{"path":"a.py","edits":[',
							},
						}
					]
				}
			),
			_chunk(
				{
					"tool_calls": [
						{
							"index": 0,
							"function": {"arguments": '{"old":"x","new":"y"}]}'},
						}
					]
				}
			),
			_chunk({}, "tool_calls"),
		],
	)

	events = await _collect(
		LiteLLMModel("gpt-4").run(
			ModelRequest(
				messages=[UserMessage(content="hi")],
				tool_display_templates={"edit": "Editing file {{ path }}"},
			)
		)
	)

	assert [event.type for event in events] == [
		"tool_call_started",
		"tool_call_display_ready",
		"assistant_message",
		"usage",
	]
	assert events[1].arguments == {"path": "a.py"}
	assert events[1].display == "Editing file a.py"
	assert events[2].tool_calls[0].arguments == {
		"path": "a.py",
		"edits": [{"old": "x", "new": "y"}],
	}
	assert events[2].tool_calls[0].display == "Editing file a.py"


async def test_litellm_emits_ready_for_a_no_argument_tool_at_stream_end(monkeypatch):
	_stream(
		monkeypatch,
		[
			_chunk({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "refresh"}}]}),
			_chunk({}, "tool_calls"),
		],
	)

	events = await _collect(LiteLLMModel("gpt-4").run(ModelRequest(messages=[UserMessage(content="hi")])))

	assert [event.type for event in events] == [
		"tool_call_started",
		"tool_call_display_ready",
		"assistant_message",
		"usage",
	]
	assert events[1].arguments == {}


def test_build_tool_call_valid():
	tc = _build_tool_call("c1", "bash", '{"command": "ls"}')
	assert tc.args == {"command": "ls"}
	assert tc.error is None


def test_build_tool_call_empty_args():
	tc = _build_tool_call("c1", "read_file", "")
	assert tc.args == {}
	assert tc.error is None


def test_build_tool_call_malformed_json():
	tc = _build_tool_call("c1", "bash", '{"command": ')
	assert tc.args == {}
	assert tc.error is not None


def test_build_tool_call_non_object():
	tc = _build_tool_call("c1", "bash", "[1, 2, 3]")
	assert tc.args == {}
	assert tc.error is not None


def test_litellm_replays_reasoning_only_to_the_same_model():
	source = AssistantMessage(
		content=[
			ThinkingContent(thinking="plan", thinking_signature="opaque"),
			TextContent(text="answer"),
		],
		api="litellm",
		provider="anthropic",
		model="anthropic/claude",
	)
	same = LiteLLMModel("anthropic/claude")
	different = LiteLLMModel("anthropic/claude-new")

	same_wire = _openai_messages([source], same, "system")[1]
	different_wire = _openai_messages([source], different, "system")[1]

	assert same_wire["reasoning_content"] == "plan"
	assert same_wire["thinking_blocks"] == [{"type": "thinking", "thinking": "plan", "signature": "opaque"}]
	assert same_wire["content"] == "answer"
	assert "reasoning_content" not in different_wire
	assert "thinking_blocks" not in different_wire
	assert different_wire["content"] == "plananswer"


def test_litellm_replays_redacted_thinking_as_its_opaque_payload():
	source = AssistantMessage(
		content=[ThinkingContent(thinking="", thinking_signature="enc", redacted=True)],
		api="litellm",
		provider="anthropic",
		model="anthropic/claude",
	)
	wire = _openai_messages([source], LiteLLMModel("anthropic/claude"), "system")[1]

	assert wire["thinking_blocks"] == [{"type": "redacted_thinking", "data": "enc"}]
	assert "reasoning_content" not in wire


def test_litellm_does_not_replay_unsigned_thinking_as_a_block():
	source = AssistantMessage(
		content=[ThinkingContent(thinking="plan")],
		api="litellm",
		provider="anthropic",
		model="anthropic/claude",
	)
	wire = _openai_messages([source], LiteLLMModel("anthropic/claude"), "system")[1]

	assert "thinking_blocks" not in wire
	assert wire["reasoning_content"] == "plan"


def test_litellm_only_persists_actual_reasoning_signatures():
	assert _reasoning_field({"reasoning_content": "plan"}) == ("plan", None)
	assert _reasoning_field({"reasoning": {"content": "plan", "signature": "opaque"}}) == (
		"plan",
		"opaque",
	)


def test_litellm_reads_signatures_from_thinking_blocks():
	blocks = _reasoning_blocks(
		{
			"reasoning_content": "plan",
			"thinking_blocks": [{"type": "thinking", "thinking": "plan", "signature": "sig"}],
		}
	)
	assert [(b.thinking, b.thinking_signature, b.redacted) for b in blocks] == [("plan", "sig", False)]

	redacted = _reasoning_blocks({"thinking_blocks": [{"type": "redacted_thinking", "data": "enc"}]})
	assert [(b.thinking, b.thinking_signature, b.redacted) for b in redacted] == [("", "enc", True)]


async def test_litellm_streams_thinking_and_seals_the_signature(monkeypatch):
	# litellm repeats the accumulated thinking on the signature chunk and blanks
	# reasoning_content there (llms/anthropic/chat/handler.py).
	_stream(
		monkeypatch,
		[
			_chunk(
				{"reasoning_content": "plan ", "thinking_blocks": [{"type": "thinking", "thinking": "plan "}]}
			),
			_chunk(
				{"reasoning_content": "more", "thinking_blocks": [{"type": "thinking", "thinking": "more"}]}
			),
			_chunk(
				{
					"reasoning_content": "",
					"thinking_blocks": [{"type": "thinking", "thinking": "plan more", "signature": "sig-1"}],
				}
			),
			_chunk({"content": "answer"}, finish_reason="stop"),
		],
	)
	events = await _collect(LiteLLMModel("anthropic/claude").run(ModelRequest(messages=[])))

	assert [e.type for e in events] == [
		"thinking_delta",
		"thinking_delta",
		"text_delta",
		"assistant_message",
		"usage",
	]
	assert [e.thinking for e in events[:2]] == ["plan ", "more"]
	content = events[-2].content
	assert [b.type for b in content] == ["thinking", "text"]
	assert (content[0].thinking, content[0].thinking_signature) == ("plan more", "sig-1")
	assert content[1].text == "answer"


async def test_litellm_starts_a_new_thinking_block_after_each_signature(monkeypatch):
	_stream(
		monkeypatch,
		[
			_chunk({"thinking_blocks": [{"type": "thinking", "thinking": "first"}]}),
			_chunk({"thinking_blocks": [{"type": "thinking", "thinking": "first", "signature": "sig-a"}]}),
			_chunk({"thinking_blocks": [{"type": "thinking", "thinking": "second"}]}),
			# litellm resets its per-block accumulator on content_block_start, so the
			# second signature restates only the second block.
			_chunk(
				{"thinking_blocks": [{"type": "thinking", "thinking": "second", "signature": "sig-b"}]},
				finish_reason="stop",
			),
		],
	)
	content = (await _collect(LiteLLMModel("anthropic/claude").run(ModelRequest(messages=[]))))[-2].content

	assert [(b.thinking, b.thinking_signature) for b in content] == [
		("first", "sig-a"),
		("second", "sig-b"),
	]


async def test_litellm_keeps_new_text_that_arrives_with_its_signature(monkeypatch):
	# Gemini signs the thought part it streams, so the text is new, not a replay.
	_stream(
		monkeypatch,
		[
			_chunk({"thinking_blocks": [{"type": "thinking", "thinking": "weigh "}]}),
			_chunk({"thinking_blocks": [{"type": "thinking", "thinking": "options", "signature": "sig-g"}]}),
			_chunk({"content": "answer"}, finish_reason="stop"),
		],
	)
	events = await _collect(LiteLLMModel("gemini/gemini-3-pro").run(ModelRequest(messages=[])))

	assert [e.thinking for e in events if e.type == "thinking_delta"] == ["weigh ", "options"]
	content = events[-2].content
	assert (content[0].thinking, content[0].thinking_signature) == ("weigh options", "sig-g")


async def test_litellm_streams_redacted_thinking_without_a_delta(monkeypatch):
	_stream(
		monkeypatch,
		[
			_chunk({"thinking_blocks": [{"type": "redacted_thinking", "data": "enc"}]}),
			_chunk({"content": "answer"}, finish_reason="stop"),
		],
	)
	events = await _collect(LiteLLMModel("anthropic/claude").run(ModelRequest(messages=[])))

	assert [e.type for e in events] == ["text_delta", "assistant_message", "usage"]
	content = events[-2].content
	assert [b.type for b in content] == ["thinking", "text"]
	assert (content[0].thinking, content[0].thinking_signature, content[0].redacted) == ("", "enc", True)


async def test_litellm_non_streaming_keeps_thinking_signatures(monkeypatch):
	async def completion(**kwargs):
		return {
			"id": "resp_1",
			"choices": [
				{
					"message": {
						"content": "answer",
						"reasoning_content": "plan",
						"thinking_blocks": [{"type": "thinking", "thinking": "plan", "signature": "sig-1"}],
					},
					"finish_reason": "stop",
				}
			],
			"usage": {"prompt_tokens": 3, "completion_tokens": 5},
		}

	monkeypatch.setattr("litellm.acompletion", completion)
	events = await _collect(LiteLLMModel("anthropic/claude").run(ModelRequest(messages=[], stream=False)))

	content = events[0].content
	assert [b.type for b in content] == ["thinking", "text"]
	assert (content[0].thinking, content[0].thinking_signature) == ("plan", "sig-1")


def test_litellm_does_not_replay_failed_assistant_response():
	failed = AssistantMessage(
		content="partial",
		api="litellm",
		provider="openai",
		model="openai/gpt",
		stop_reason="error",
		error_message="network failed",
	)

	assert _openai_messages([failed], LiteLLMModel("openai/gpt"), "system") == [
		{"role": "system", "content": "system"}
	]


def test_litellm_drops_results_answering_a_dropped_assistant_turn():
	aborted = AssistantMessage(
		content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})],
		api="litellm",
		provider="openai",
		model="openai/gpt",
		stop_reason="aborted",
	)
	repair = ToolResult(tool_call_id="c1", name="read_file", content="interrupted", is_error=True)

	# the call and its answer must both be dropped
	assert _openai_messages([aborted, repair], LiteLLMModel("openai/gpt"), "system") == [
		{"role": "system", "content": "system"}
	]


def test_litellm_marks_cache_breakpoints_for_anthropic():
	tools = [
		{"type": "function", "function": {"name": "read_file", "parameters": {}}},
		{"type": "function", "function": {"name": "bash", "parameters": {}}},
	]
	request = ModelRequest(messages=[UserMessage(content="hi")], tools=tools, system_prompt="system")

	kwargs = LiteLLMModel("anthropic/claude")._completion_kwargs(request)

	assert kwargs["messages"][0]["cache_control"] == {"type": "ephemeral"}
	assert kwargs["messages"][-1]["cache_control"] == {"type": "ephemeral"}
	assert "cache_control" not in kwargs["tools"][0]
	assert kwargs["tools"][1]["cache_control"] == {"type": "ephemeral"}
	assert "cache_control" not in tools[1]


@pytest.mark.parametrize(
	("name", "provider"),
	[
		("anthropic/claude", "gateway"),
		("claude-sonnet-4-20250514", None),
		("bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0", None),
		("vertex_ai/claude-sonnet-4@20250514", None),
		("openrouter/anthropic/claude-sonnet-4", None),
		("openrouter/~anthropic/claude-sonnet-latest", None),
		("openrouter/google/gemini-2.5-pro", None),
		("openrouter/minimax/minimax-m2.5", None),
		("azure_ai/claude-sonnet-4-5", None),
		("databricks/databricks-claude-sonnet-4", None),
	],
)
def test_litellm_marks_cache_breakpoints_from_the_wire_model(name, provider):
	request = ModelRequest(messages=[UserMessage(content="hi")], system_prompt="system")

	kwargs = LiteLLMModel(name, provider=provider)._completion_kwargs(request)

	assert all(message["cache_control"] == {"type": "ephemeral"} for message in kwargs["messages"])


def test_litellm_cache_breakpoint_lands_on_the_last_tool_result():
	call = AssistantMessage(
		content=[ToolCall(id="c1", name="bash", arguments={"command": "ls"})],
		api="litellm",
		provider="anthropic",
		model="anthropic/claude",
	)
	result = ToolResult(tool_call_id="c1", name="bash", content="ok")
	request = ModelRequest(messages=[UserMessage(content="hi"), call, result], system_prompt="system")

	messages = LiteLLMModel("anthropic/claude")._completion_kwargs(request)["messages"]

	assert messages[-1]["role"] == "tool"
	assert messages[-1]["cache_control"] == {"type": "ephemeral"}
	assert "cache_control" not in messages[1]


@pytest.mark.parametrize(
	"name",
	[
		"openai/gpt",
		"vertex_ai/gemini-2.5-pro",
		"openrouter/openai/gpt-5",
		"databricks/databricks-meta-llama-3-3-70b-instruct",
	],
)
def test_litellm_skips_cache_breakpoints_for_other_providers(name):
	tools = [{"type": "function", "function": {"name": "bash", "parameters": {}}}]
	request = ModelRequest(messages=[UserMessage(content="hi")], tools=tools, system_prompt="system")

	kwargs = LiteLLMModel(name)._completion_kwargs(request)

	assert all("cache_control" not in message for message in kwargs["messages"])
	assert kwargs["tools"] is tools
	assert "cache_control" not in tools[0]


def test_usage_event_maps_anthropic_cache_fields():
	usage = _usage_event(
		{
			"prompt_tokens": 120,
			"completion_tokens": 5,
			"cache_read_input_tokens": 100,
			"cache_creation_input_tokens": 15,
		},
		cost=0.01,
	)

	assert (usage.input_tokens, usage.output_tokens) == (120, 5)
	assert (usage.cache_read_tokens, usage.cache_write_tokens) == (100, 15)


def test_usage_event_falls_back_to_prompt_tokens_details():
	usage = _usage_event(
		{
			"prompt_tokens": 50,
			"completion_tokens": 3,
			"prompt_tokens_details": {"cached_tokens": 40, "cache_creation_tokens": 6},
		},
		cost=0.0,
	)

	assert (usage.cache_read_tokens, usage.cache_write_tokens) == (40, 6)


def test_usage_event_maps_cache_write_tokens_detail():
	usage = _usage_event(
		{
			"prompt_tokens": 50,
			"completion_tokens": 3,
			"prompt_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 6},
		},
		cost=0.0,
	)

	assert (usage.cache_read_tokens, usage.cache_write_tokens) == (40, 6)
