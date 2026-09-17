import pytest
from pydantic import ValidationError

from flow_harness.events import (
	ApprovalRequired,
	AssistantMessage,
	DisplaySegment,
	ModelChanged,
	Retry,
	Rewind,
	RunEnded,
	RunError,
	RunStarted,
	TextContent,
	TextDelta,
	ThinkingContent,
	ThinkingDelta,
	ToolCall,
	ToolCallDisplayReady,
	ToolCallStarted,
	ToolResult,
	Usage,
	UserMessage,
	parse_event,
)


def test_durable_classification():
	durable = [
		RunStarted,
		UserMessage,
		AssistantMessage,
		ToolResult,
		Usage,
		ApprovalRequired,
		Rewind,
		ModelChanged,
		RunEnded,
		RunError,
	]
	live = [TextDelta, ThinkingDelta, ToolCallStarted, ToolCallDisplayReady, Retry]

	assert all(event.durable for event in durable)
	assert not any(event.durable for event in live)


def test_provider_state_round_trips_on_every_block():
	message = AssistantMessage(
		content=[
			TextContent(text="answer", provider_state={"id": "msg_1", "phase": "final_answer"}),
			ThinkingContent(thinking="plan", thinking_signature="sig", provider_state={"item": {"id": "r1"}}),
			ToolCall(id="c1", name="bash", arguments={"command": "pwd"}, provider_state={"item_id": "fc_1"}),
		],
		stop_reason="tool_use",
	)

	restored = parse_event(message.model_dump(exclude_none=True))

	assert isinstance(restored, AssistantMessage)
	assert restored.content[0].provider_state == {"id": "msg_1", "phase": "final_answer"}
	assert restored.content[1].provider_state == {"item": {"id": "r1"}}
	assert restored.content[1].thinking_signature == "sig"
	assert restored.tool_calls[0].provider_state == {"item_id": "fc_1"}


def test_unknown_fields_are_still_rejected():
	with pytest.raises(ValidationError):
		parse_event({"seq": 1, "type": "assistant_message", "text": "pre-release shape"})


def test_unknown_event_type_is_rejected():
	with pytest.raises(ValidationError):
		parse_event({"seq": 1, "type": "not_an_event"})


def test_assistant_content_string_sugar_and_views():
	message = AssistantMessage(
		content=[
			TextContent(text="answer"),
			ThinkingContent(thinking="plan"),
			ToolCall(id="c1", name="bash", arguments={"command": "pwd"}),
		]
	)
	assert message.text == "answer"
	assert message.thinking_text == "plan"
	assert message.tool_calls[0].args == {"command": "pwd"}

	sugar = AssistantMessage(content="hello")
	assert [block.type for block in sugar.content] == ["text"]
	assert AssistantMessage(content="").content == []


def test_retry_event_shape():
	scheduled = Retry(status="scheduled", attempt=2, max_attempts=4, delay_seconds=0.5, kind="overloaded")
	assert scheduled.model_dump(exclude_none=True) == {
		"type": "retry",
		"status": "scheduled",
		"attempt": 2,
		"max_attempts": 4,
		"delay_seconds": 0.5,
		"kind": "overloaded",
	}
	assert Retry(status="exhausted", attempt=3).max_attempts is None


def test_tool_call_display_ready_round_trips_as_live_metadata():
	event = parse_event(
		{
			"type": "tool_call_display_ready",
			"id": "c1",
			"name": "edit",
			"arguments": {"path": "src/app.py"},
			"display": [{"text": "Editing file "}, {"text": "src/app.py", "arg": "path"}],
		}
	)
	assert isinstance(event, ToolCallDisplayReady)
	assert event.arguments["path"] == "src/app.py"
	assert event.display == [
		DisplaySegment(text="Editing file "),
		DisplaySegment(text="src/app.py", arg="path"),
	]
	assert event.durable is False

	# a display persisted by an early flat-string build reads as one plain segment
	legacy = ToolCall.model_validate(
		{"id": "c1", "name": "edit", "arguments": {}, "display": "Editing file src/app.py"}
	)
	assert legacy.display == [DisplaySegment(text="Editing file src/app.py")]


def test_the_subagent_tag_rides_on_events_and_is_absent_from_untagged_rows():
	tagged = parse_event({"type": "run_ended", "seq": 1, "reason": "done", "subagent_id": "c1"})
	assert tagged.subagent_id == "c1"
	assert "subagent_id" not in ToolResult(tool_call_id="c", name="read", content="").model_dump(
		exclude_none=True
	)
