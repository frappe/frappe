import asyncio

import httpx
import pytest

from flow_harness.events import (
	AssistantMessage,
	DisplaySegment,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_harness.model import (
	_NATIVE_PROVIDERS,
	LiteLLMModel,
	MockModel,
	ModelRequest,
	ProviderError,
	get_model,
	register_provider,
)
from flow_harness.model.discovery import context_window_for
from flow_harness.model.litellm import (
	_build_tool_call,
	_openai_messages,
	_stop_reason,
	_usage_event,
)
from flow_harness.model.providers.codex import CodexModel
from flow_harness.model.tool_display import (
	extract_tool_call_display_metadata,
	tool_call_display_ready_event,
)

_CACHE = {"type": "ephemeral"}


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


def test_tool_call_display_is_early_bounded_and_complete():
	partial = '{"path":"ui/App.vue","edits":[{"old":"' + ("x" * 10_000)

	assert extract_tool_call_display_metadata(partial) == {"path": "ui/App.vue"}
	assert extract_tool_call_display_metadata({"command": "x" * 1_000}) == {"command": "x" * 512}

	template = "Searching {{ source }} for {{ query }}"

	def ready(template, arguments, **kwargs):
		event = tool_call_display_ready_event(
			"call-1", "web_search", arguments, display_template=template, **kwargs
		)
		if event is None or event.display is None:
			return None
		return "".join(segment.text for segment in event.display)

	assert ready(template, '{"source":"the web","query":"Flo') is None
	assert ready(template, '{"source":"the web","query":"Flow","options":[') == "Searching the web for Flow"
	assert ready("Opening page {{ page }}", '{"page":1') is None
	assert ready("Opening page {{ page }}", '{"page":10}', complete=True) == "Opening page 10"

	# a static label is ready before any argument arrives
	static = tool_call_display_ready_event("call-1", "bash", "", display_template="Running command")
	assert static is not None
	assert (static.arguments, static.display) == ({}, [DisplaySegment(text="Running command")])


async def test_mock_echoes_with_deltas_only_when_streaming():
	events = await _collect(MockModel().run(ModelRequest(messages=[UserMessage(content="hi there")])))
	types = [e.type for e in events]
	assert types[-2:] == ["assistant_message", "usage"]
	assert all(t == "text_delta" for t in types[:-2])
	assert len(types) > 2  # streamed as several deltas

	assistant = events[-2]
	assert assistant.text == "Mock reply to: hi there"
	assert "".join(e.text for e in events[:-2]) == assistant.text

	quiet = await _collect(MockModel().run(ModelRequest(messages=[UserMessage(content="hi")], stream=False)))
	assert [e.type for e in quiet] == ["assistant_message", "usage"]


async def test_mock_scripted_replies_multi_turn():
	call = ToolCall(id="c1", name="web_search", arguments={"query": "Flow"})
	model = MockModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])
	request = ModelRequest(
		messages=[UserMessage(content="go")],
		tool_display_templates={"web_search": "Searching the web for {{ query }}"},
	)

	first = await _collect(model.run(request))
	assert [e.type for e in first] == [
		"tool_call_started",
		"tool_call_display_ready",
		"assistant_message",
		"usage",
	]
	assert first[0].id == "c1" and first[0].name == "web_search"
	assert first[1].arguments == {"query": "Flow"}
	assert first[2].tool_calls[0].args == {"query": "Flow"}
	# the display renders on the live event and the durable call alike
	display = [
		DisplaySegment(text="Searching the web for "),
		DisplaySegment(text="Flow", arg="query"),
	]
	assert first[1].display == display
	assert first[2].tool_calls[0].display == display

	second = await _collect(model.run(request))
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
	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 0)
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


def test_get_model_dispatches_on_the_name_prefix():
	assert isinstance(get_model("mock"), MockModel)

	async def refresh_auth(rejected_token):
		raise AssertionError("never called here")

	codex = get_model("codex/gpt-test", api_key="token", refresh_auth=refresh_auth)
	assert isinstance(codex, CodexModel)
	assert codex._refresh_auth is refresh_auth

	sentinel = MockModel()
	register_provider("dummy", lambda name, **kwargs: sentinel)
	try:
		assert get_model("dummy/whatever") is sentinel
	finally:
		_NATIVE_PROVIDERS.pop("dummy", None)

	# any other prefix falls through to litellm
	model = get_model("anthropic/claude-3-5-sonnet", api_key="sk-test", api_base="https://x")
	assert isinstance(model, LiteLLMModel)
	assert (model.name, model._api_key, model._api_base) == (
		"anthropic/claude-3-5-sonnet",
		"sk-test",
		"https://x",
	)


def test_gateway_model_takes_limits_from_the_id_behind_its_prefix(monkeypatch):
	catalog = {
		"custom_openai/openai/gpt-x": {"max_input_tokens": None},  # LiteLLM's stub for a gateway id
		"openai/gpt-x": {"max_input_tokens": 400_000, "max_output_tokens": 64_000},
	}

	def get_model_info(name):
		if name not in catalog:
			raise Exception("This model isn't mapped yet.")
		return catalog[name]

	monkeypatch.setattr("litellm.get_model_info", get_model_info)

	gateway = LiteLLMModel("custom_openai/openai/gpt-x")
	assert (gateway.context_window, gateway.max_output_tokens) == (400_000, 64_000)
	assert context_window_for("custom_openai/openai/gpt-x") == 400_000
	assert LiteLLMModel("custom_openai/vendor/unmapped").context_window is None


def test_opencode_go_routes_each_family_to_its_wire_protocol():
	go = "https://opencode.ai/zen/go/v1"
	cases = [
		# (name, api_base override, litellm route, base sent)
		("opencode-go/grok-4.5", None, "openai/grok-4.5", go),
		("opencode-go/minimax-m3", None, "anthropic/minimax-m3", f"{go}/messages"),
		("opencode-go/qwen3.7-max", None, "anthropic/qwen3.7-max", f"{go}/messages"),
		("opencode-go/kimi-k3", "https://proxy.test/v1", "openai/kimi-k3", "https://proxy.test/v1"),
		(
			"opencode-go/minimax-m3",
			"https://proxy.test/v1",
			"anthropic/minimax-m3",
			"https://proxy.test/v1/messages",
		),
		# litellm appends /v1/messages itself when the base is not a versioned root
		("opencode-go/minimax-m3", "https://proxy.test", "anthropic/minimax-m3", "https://proxy.test"),
	]
	for name, api_base, route, base in cases:
		model = get_model(name, api_key="sk-go", api_base=api_base)
		assert isinstance(model, LiteLLMModel), name
		assert (model.name, model._api_base, model.provider, model.model) == (
			route,
			base,
			"opencode-go",
			name,
		), (name, api_base)

	with pytest.raises(ValueError, match="opencode-go/<model-id>"):
		get_model("opencode-go")


def test_stop_reason_prefers_the_provider_signal_over_tool_presence():
	assert _stop_reason("length", has_tools=True) == "length"
	assert _stop_reason("content_filter", has_tools=True) == "error"
	# a plain stop is still upgraded, which is why has_tools exists
	assert _stop_reason("stop", has_tools=True) == "tool_use"
	assert _stop_reason(None, has_tools=True) == "tool_use"
	assert _stop_reason("tool_calls", has_tools=False) == "tool_use"


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
	display = [DisplaySegment(text="Editing file "), DisplaySegment(text="a.py", arg="path")]
	assert events[1].arguments == {"path": "a.py"}
	assert events[1].display == display
	assert events[2].tool_calls[0].arguments == {
		"path": "a.py",
		"edits": [{"old": "x", "new": "y"}],
	}
	assert events[2].tool_calls[0].display == display


async def test_litellm_settles_tool_calls_when_the_stream_ends(monkeypatch):
	cases = [
		# a no-argument tool is ready only once the stream ends
		({"name": "refresh"}, "tool_calls", {}, "tool_use"),
		# a truncated call is still reported, but stays "length" so it never runs
		({"name": "bash", "arguments": '{"command":"ls"}'}, "length", {"command": "ls"}, "length"),
	]
	for function, finish_reason, arguments, stop_reason in cases:
		_stream(
			monkeypatch,
			[
				_chunk({"tool_calls": [{"index": 0, "id": "c1", "function": function}]}),
				_chunk({}, finish_reason),
			],
		)

		events = await _collect(LiteLLMModel("gpt-4").run(ModelRequest(messages=[UserMessage(content="hi")])))

		assert [event.type for event in events] == [
			"tool_call_started",
			"tool_call_display_ready",
			"assistant_message",
			"usage",
		], finish_reason
		assert events[1].arguments == arguments, finish_reason
		assert (events[2].tool_calls[0].id, events[2].stop_reason) == ("c1", stop_reason), finish_reason


def test_build_tool_call_reports_bad_arguments_instead_of_raising():
	cases = [
		('{"command": "ls"}', {"command": "ls"}, False),
		("", {}, False),
		('{"command": ', {}, True),  # malformed JSON
		("[1, 2, 3]", {}, True),  # not an object
	]
	for raw, args, failed in cases:
		tc = _build_tool_call("c1", "bash", raw)
		assert tc.args == args, raw
		assert (tc.error is not None) is failed, raw


def test_litellm_replays_reasoning_only_to_the_same_model():
	def wire(content, model="anthropic/claude", target="anthropic/claude"):
		source = AssistantMessage(
			content=content, api="litellm", provider=model.split("/", 1)[0], model=model
		)
		return _openai_messages([source], LiteLLMModel(target), "system")[1]

	signed = [ThinkingContent(thinking="plan", thinking_signature="opaque"), TextContent(text="answer")]
	same = wire(signed)
	assert same["reasoning_content"] == "plan"
	assert same["thinking_blocks"] == [{"type": "thinking", "thinking": "plan", "signature": "opaque"}]
	assert same["content"] == "answer"

	# another model gets the thinking as plain text
	different = wire(signed, target="anthropic/claude-new")
	assert "reasoning_content" not in different
	assert "thinking_blocks" not in different
	assert different["content"] == "plananswer"

	# redacted thinking replays as its opaque payload only
	redacted = wire([ThinkingContent(thinking="", thinking_signature="enc", redacted=True)])
	assert redacted["thinking_blocks"] == [{"type": "redacted_thinking", "data": "enc"}]
	assert "reasoning_content" not in redacted

	# unsigned thinking cannot be verified upstream, so it never goes out as a block
	unsigned = wire([ThinkingContent(thinking="plan")])
	assert "thinking_blocks" not in unsigned
	assert unsigned["reasoning_content"] == "plan"

	# Groq rejects reasoning_content on its own turns
	groq = "groq/openai/gpt-oss-120b"
	groq_wire = wire([ThinkingContent(thinking="plan"), TextContent(text="answer")], groq, groq)
	assert "reasoning_content" not in groq_wire
	assert groq_wire["content"] == "answer"


async def test_litellm_streams_thinking_and_seals_each_signature(monkeypatch):
	cases = [
		(
			# litellm repeats the accumulated thinking on the signature chunk and blanks
			# reasoning_content there (llms/anthropic/chat/handler.py)
			"anthropic/claude",
			[
				{
					"reasoning_content": "plan ",
					"thinking_blocks": [{"type": "thinking", "thinking": "plan "}],
				},
				{"reasoning_content": "more", "thinking_blocks": [{"type": "thinking", "thinking": "more"}]},
				{
					"reasoning_content": "",
					"thinking_blocks": [{"type": "thinking", "thinking": "plan more", "signature": "sig-1"}],
				},
			],
			["plan ", "more"],
			[("plan more", "sig-1", False)],
		),
		(
			# a signature seals its block; litellm resets its per-block accumulator on
			# content_block_start, so the second signature restates only the second block
			"anthropic/claude",
			[
				{"thinking_blocks": [{"type": "thinking", "thinking": "first"}]},
				{"thinking_blocks": [{"type": "thinking", "thinking": "first", "signature": "sig-a"}]},
				{"thinking_blocks": [{"type": "thinking", "thinking": "second"}]},
				{"thinking_blocks": [{"type": "thinking", "thinking": "second", "signature": "sig-b"}]},
			],
			["first", "second"],
			[("first", "sig-a", False), ("second", "sig-b", False)],
		),
		(
			# Gemini signs the thought part it streams, so the text is new, not a replay
			"gemini/gemini-3-pro",
			[
				{"thinking_blocks": [{"type": "thinking", "thinking": "weigh "}]},
				{"thinking_blocks": [{"type": "thinking", "thinking": "options", "signature": "sig-g"}]},
			],
			["weigh ", "options"],
			[("weigh options", "sig-g", False)],
		),
		(
			# redacted thinking streams no delta
			"anthropic/claude",
			[{"thinking_blocks": [{"type": "redacted_thinking", "data": "enc"}]}],
			[],
			[("", "enc", True)],
		),
	]
	for model, deltas, streamed, blocks in cases:
		_stream(monkeypatch, [*map(_chunk, deltas), _chunk({"content": "answer"}, finish_reason="stop")])
		events = await _collect(LiteLLMModel(model).run(ModelRequest(messages=[])))

		assert [e.type for e in events] == ["thinking_delta"] * len(streamed) + [
			"text_delta",
			"assistant_message",
			"usage",
		], blocks
		assert [e.thinking for e in events[: len(streamed)]] == streamed, blocks
		content = events[-2].content
		assert [(b.thinking, b.thinking_signature, b.redacted) for b in content[:-1]] == blocks
		assert content[-1].text == "answer", blocks


async def test_litellm_non_streaming_keeps_thinking_signatures(monkeypatch):
	cases = [
		(
			{
				"reasoning_content": "plan",
				"thinking_blocks": [{"type": "thinking", "thinking": "plan", "signature": "sig-1"}],
			},
			("plan", "sig-1", False),
		),
		({"thinking_blocks": [{"type": "redacted_thinking", "data": "enc"}]}, ("", "enc", True)),
		# a plain reasoning field carries a signature only when it states one
		({"reasoning_content": "plan"}, ("plan", None, False)),
		({"reasoning": {"content": "plan", "signature": "opaque"}}, ("plan", "opaque", False)),
	]
	for reasoning, thinking in cases:

		async def completion(**kwargs):
			return {
				"id": "resp_1",
				"choices": [{"message": {"content": "answer", **reasoning}, "finish_reason": "stop"}],
				"usage": {"prompt_tokens": 3, "completion_tokens": 5},
			}

		monkeypatch.setattr("litellm.acompletion", completion)
		events = await _collect(LiteLLMModel("anthropic/claude").run(ModelRequest(messages=[], stream=False)))

		content = events[0].content
		assert [b.type for b in content] == ["thinking", "text"], reasoning
		assert (content[0].thinking, content[0].thinking_signature, content[0].redacted) == thinking


def test_litellm_drops_failed_turns_and_the_results_answering_them():
	def turn(content, stop_reason):
		return AssistantMessage(
			content=content,
			api="litellm",
			provider="openai",
			model="openai/gpt",
			stop_reason=stop_reason,
		)

	failed = turn("partial", "error")
	aborted = turn([ToolCall(id="c1", name="read", arguments={"path": "a.txt"})], "aborted")
	repair = ToolResult(tool_call_id="c1", name="read", content="interrupted", is_error=True)

	# a call and its answer must both be dropped
	assert _openai_messages([failed, aborted, repair], LiteLLMModel("openai/gpt"), "system") == [
		{"role": "system", "content": "system"}
	]


def test_litellm_marks_cache_breakpoints_from_the_wire_model():
	tools = [
		{"type": "function", "function": {"name": "read", "parameters": {}}},
		{"type": "function", "function": {"name": "bash", "parameters": {}}},
	]
	request = ModelRequest(messages=[UserMessage(content="hi")], tools=tools, system_prompt="system")
	cases = [
		("anthropic/claude", "gateway", True),
		("claude-sonnet-4-20250514", None, True),
		("bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0", None, True),
		("vertex_ai/claude-sonnet-4@20250514", None, True),
		("openrouter/anthropic/claude-sonnet-4", None, True),
		("openrouter/~anthropic/claude-sonnet-latest", None, True),
		("openrouter/google/gemini-2.5-pro", None, True),
		("openrouter/minimax/minimax-m2.5", None, True),
		("azure_ai/claude-sonnet-4-5", None, True),
		("databricks/databricks-claude-sonnet-4", None, True),
		("openai/gpt", None, False),
		("vertex_ai/gemini-2.5-pro", None, False),
		("openrouter/openai/gpt-5", None, False),
		("databricks/databricks-meta-llama-3-3-70b-instruct", None, False),
	]
	for name, provider, caches in cases:
		kwargs = LiteLLMModel(name, provider=provider)._completion_kwargs(request)

		mark = _CACHE if caches else None
		# the system prompt, the last user turn and the last tool
		assert [message.get("cache_control") for message in kwargs["messages"]] == [mark, mark], name
		assert [tool.get("cache_control") for tool in kwargs["tools"]] == [None, mark], name
		if not caches:
			assert kwargs["tools"] is tools, name
	assert all("cache_control" not in tool for tool in tools)

	# a trailing tool result takes the last breakpoint
	call = AssistantMessage(
		content=[ToolCall(id="c1", name="bash", arguments={"command": "ls"})],
		api="litellm",
		provider="anthropic",
		model="anthropic/claude",
	)
	result = ToolResult(tool_call_id="c1", name="bash", content="ok")
	request = ModelRequest(messages=[UserMessage(content="hi"), call, result], system_prompt="system")

	messages = LiteLLMModel("anthropic/claude")._completion_kwargs(request)["messages"]

	assert [(message["role"], message.get("cache_control")) for message in messages] == [
		("system", _CACHE),
		("user", None),
		("assistant", None),
		("tool", _CACHE),
	]


async def test_litellm_usage_maps_cache_tokens_and_the_stream_cost(monkeypatch):
	cases = [
		({"cache_read_input_tokens": 100, "cache_creation_input_tokens": 15}, (100, 15)),
		({"prompt_tokens_details": {"cached_tokens": 40, "cache_creation_tokens": 6}}, (40, 6)),
		({"prompt_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 6}}, (40, 6)),
	]
	for fields, cache in cases:
		usage = _usage_event({"prompt_tokens": 120, "completion_tokens": 5, **fields})
		assert (usage.input_tokens, usage.output_tokens) == (120, 5), fields
		assert (usage.cache_read_tokens, usage.cache_write_tokens) == cache, fields

	# a stream states its cost on the final usage chunk, which has no choices
	_stream(
		monkeypatch,
		[
			_chunk({"content": "hi"}, finish_reason="stop"),
			{"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "cost": 0.002}},
		],
	)
	events = await _collect(LiteLLMModel("openai/gpt-4o").run(ModelRequest(messages=[])))

	assert events[-1].cost == 0.002
