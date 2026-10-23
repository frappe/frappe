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


def test_parse_event_reads_tagged_rows_and_rejects_unknown_shapes():
	tagged = parse_event({"type": "run_ended", "seq": 1, "reason": "done", "subagent_id": "c1"})
	assert tagged.subagent_id == "c1"
	assert "subagent_id" not in ToolResult(tool_call_id="c", name="read", content="").model_dump(
		exclude_none=True
	)

	for row in (
		{"seq": 1, "type": "assistant_message", "text": "pre-release shape"},  # an unknown field
		{"seq": 1, "type": "not_an_event"},
	):
		with pytest.raises(ValidationError):
			parse_event(row)


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
