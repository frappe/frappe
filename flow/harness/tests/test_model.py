from flow_server.events import AssistantMessage, ToolCall
from flow_server.model import (
	_REGISTRY,
	LiteLLMModel,
	MockModel,
	get_model,
	register_provider,
)
from flow_server.model.model import _build_tool_call


async def _collect(gen):
	return [ev async for ev in gen]


async def test_mock_streaming_sequence():
	events = await _collect(MockModel().run([{"role": "user", "content": "hi there"}]))
	types = [e.type for e in events]
	assert types[-2:] == ["assistant_message", "usage"]
	assert all(t == "text_delta" for t in types[:-2])
	assert len(types) > 2  # streamed as several deltas

	assistant = events[-2]
	assert assistant.text == "Mock reply to: hi there"
	assert "".join(e.text for e in events[:-2]) == assistant.text


async def test_mock_non_streaming_has_no_deltas():
	events = await _collect(
		MockModel().run([{"role": "user", "content": "hi"}], stream=False)
	)
	assert [e.type for e in events] == ["assistant_message", "usage"]


async def test_mock_scripted_replies_multi_turn():
	call = ToolCall(id="c1", name="bash", args={"command": "ls"})
	model = MockModel(
		replies=[AssistantMessage(text="", tool_calls=[call]), AssistantMessage(text="done")]
	)

	first = await _collect(model.run([{"role": "user", "content": "go"}]))
	assert [e.type for e in first] == ["tool_call_started", "assistant_message", "usage"]
	assert first[0].id == "c1" and first[0].name == "bash"
	assert first[1].tool_calls[0].args == {"command": "ls"}

	second = await _collect(model.run([{"role": "user", "content": "go"}]))
	assert second[-2].text == "done"


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
