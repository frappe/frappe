import asyncio

import httpx
import pytest

from flow_server.events import AssistantMessage, TextContent, ThinkingContent, ToolCall, UserMessage
from flow_server.model import (
	_REGISTRY,
	LiteLLMModel,
	MockModel,
	ModelRequest,
	ProviderError,
	get_model,
	register_provider,
)
from flow_server.model.model import _build_tool_call, _openai_messages, _reasoning


async def _collect(gen):
	return [ev async for ev in gen]


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


async def test_mock_scripted_replies_multi_turn():
	call = ToolCall(id="c1", name="bash", arguments={"command": "ls"})
	model = MockModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])

	first = await _collect(model.run(ModelRequest(messages=[UserMessage(content="go")])))
	assert [e.type for e in first] == ["tool_call_started", "assistant_message", "usage"]
	assert first[0].id == "c1" and first[0].name == "bash"
	assert first[1].tool_calls[0].args == {"command": "ls"}

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


async def test_litellm_disables_sdk_retries_and_normalizes_provider_failure(monkeypatch):
	seen_kwargs = {}

	async def completion(**kwargs):
		import litellm

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


def test_opencode_go_routes_openai_family_to_chat_completions():
	model = get_model("opencode-go/grok-4.5", api_key="sk-go")
	assert isinstance(model, LiteLLMModel)
	assert model.name == "openai/grok-4.5"
	assert model._api_base == "https://opencode.ai/zen/go/v1"
	assert model._api_key == "sk-go"


def test_opencode_go_routes_anthropic_family_to_messages():
	for name, expected in (
		("opencode-go/minimax-m3", "anthropic/minimax-m3"),
		("opencode-go/qwen3.7-max", "anthropic/qwen3.7-max"),
	):
		model = get_model(name, api_key="sk-go")
		assert isinstance(model, LiteLLMModel)
		assert model.name == expected
		assert model._api_base == "https://opencode.ai/zen/go/v1/messages"


def _api_base(name: str, api_base: str) -> str | None:
	model = get_model(name, api_base=api_base)
	assert isinstance(model, LiteLLMModel)
	return model._api_base


def test_opencode_go_honours_api_base_override():
	assert _api_base("opencode-go/kimi-k3", "https://proxy.test/v1") == "https://proxy.test/v1"
	assert _api_base("opencode-go/minimax-m3", "https://proxy.test/v1") == "https://proxy.test/v1/messages"
	# litellm appends /v1/messages itself when the base is not a versioned root.
	assert _api_base("opencode-go/minimax-m3", "https://proxy.test") == "https://proxy.test"


def test_opencode_go_rejects_bare_prefix():
	with pytest.raises(ValueError, match="opencode-go/<model-id>"):
		get_model("opencode-go")


def test_register_provider_dispatch():
	sentinel = MockModel()
	register_provider("dummy", lambda name, **kwargs: sentinel)
	try:
		assert get_model("dummy/whatever") is sentinel
	finally:
		_REGISTRY.pop("dummy", None)


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
	assert same_wire["content"] == "answer"
	assert "reasoning_content" not in different_wire
	assert different_wire["content"] == "plananswer"


def test_litellm_only_persists_actual_reasoning_signatures():
	assert _reasoning({"reasoning_content": "plan"}) == ("plan", None)
	assert _reasoning({"reasoning": {"content": "plan", "signature": "opaque"}}) == (
		"plan",
		"opaque",
	)


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
