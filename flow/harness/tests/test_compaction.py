"""Compaction planning and summarization: deterministic estimation, turn-safe
boundaries, prompt selection, and the summarizer's silent tool-less model call."""

import json

import pytest

from flow.agent.compaction import (
	KEEP_RECENT_TOKENS,
	MESSAGE_OVERHEAD_TOKENS,
	TOOL_OVERHEAD_TOKENS,
	build_summary_prompt,
	calculate_compaction_input_limit,
	calculate_reserved_output_tokens,
	compact_events,
	estimate_context_tokens,
	estimate_text_tokens,
	plan_all,
	plan_keep_recent,
	serialize_messages,
	summarize,
)
from flow.events import (
	AssistantMessage,
	Compaction,
	TextContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow.model.mock import MockModel
from flow.session.transcript import compaction_summary_message

BIG = "x" * (KEEP_RECENT_TOKENS * 4)  # one message that alone overflows the kept tail


def _user(seq, content):
	return UserMessage(seq=seq, content=content)


def _assistant(seq, text="", call_ids=()):
	content = [TextContent(text=text)] if text else []
	content += [ToolCall(id=cid, name="read_file", arguments={"path": "a.txt"}) for cid in call_ids]
	return AssistantMessage(seq=seq, content=content, stop_reason="tool_use" if call_ids else "stop")


def _result(seq, call_id, content, is_error=False):
	return ToolResult(seq=seq, tool_call_id=call_id, name="read_file", content=content, is_error=is_error)


# --- estimation -------------------------------------------------------------


def test_text_estimation_is_chars_over_four_rounded_up():
	assert estimate_text_tokens("") == 0
	assert estimate_text_tokens("abcd") == 1
	assert estimate_text_tokens("abcde") == 2


def test_context_estimate_counts_system_tools_and_messages():
	schema = {"type": "function"}
	total = estimate_context_tokens("s" * 8, [schema], [_user(1, "x" * 40)])
	expected = (
		2  # system prompt
		+ TOOL_OVERHEAD_TOKENS
		+ estimate_text_tokens(json.dumps(schema))
		+ MESSAGE_OVERHEAD_TOKENS
		+ 10  # message content
	)
	assert total == expected


# --- planning ---------------------------------------------------------------


def test_keep_recent_needs_something_old_enough_to_replace():
	assert plan_keep_recent([]) is None
	assert plan_keep_recent([_user(1, "hi")]) is None
	# a small conversation fits entirely inside the kept tail
	assert plan_keep_recent([_user(1, "hi"), _assistant(2, "yo")]) is None


def test_keep_recent_cuts_at_the_user_turn_that_starts_the_kept_tail():
	messages = [
		_user(1, BIG),
		_assistant(2, "first answer"),
		_user(3, "second question"),
		_assistant(4, "second answer"),
	]

	plan = plan_keep_recent(messages)

	assert plan is not None
	assert plan.compact_up_to_seq == 2  # user 3 starts the kept tail
	assert [m.seq for m in plan.messages_to_summarize] == [1, 2]
	assert plan.previous_summary is None


def test_cut_never_lands_on_a_tool_result():
	# the big message is a tool result; the cut snaps forward past it to the next
	# assistant start, keeping the call and its result together in the replaced side
	messages = [
		_user(1, "start"),
		_assistant(2, "working", call_ids=["c1"]),
		_result(3, "c1", BIG),
		_assistant(4, "final"),
	]

	plan = plan_keep_recent(messages)

	assert plan is not None
	assert plan.compact_up_to_seq == 3
	assert [m.seq for m in plan.messages_to_summarize] == [1, 2, 3]


def test_a_single_turn_cannot_be_compacted_without_splitting():
	messages = [_user(1, BIG), _assistant(2, call_ids=["c1"]), _result(3, "c1", "data")]

	assert plan_keep_recent(messages) is None


def test_plan_splits_a_previous_summary_for_the_update_prompt():
	messages = [
		compaction_summary_message("old summary", seq=5),
		_user(6, "more work"),
		_assistant(7, "did it"),
	]

	plan = plan_all(messages)

	assert plan is not None
	assert plan.previous_summary == "old summary"
	assert [m.seq for m in plan.messages_to_summarize] == [6, 7]
	assert plan.compact_up_to_seq == 7
	prompt = build_summary_prompt(plan)
	assert "<previous-summary>\nold summary\n</previous-summary>" in prompt
	assert "NEW conversation messages" in prompt  # the update prompt, not the initial one


def test_initial_prompt_and_instruction_appendix():
	plan = plan_all([_user(1, "hello")])
	assert plan is not None

	prompt = build_summary_prompt(plan, summary_instructions="focus on tests")

	assert "<previous-summary>" not in prompt
	assert "context checkpoint summary" in prompt
	assert prompt.endswith("Additional focus: focus on tests")


def test_plan_all_takes_everything_and_rejects_nothing_durable():
	assert plan_all([]) is None
	assert plan_all([UserMessage(content="never committed")]) is None  # no seq, no boundary

	plan = plan_all([_user(1, "a"), _assistant(2, "b")])
	assert plan is not None
	assert plan.compact_up_to_seq == 2
	assert len(plan.messages_to_summarize) == 2


# --- serialization + summarizer --------------------------------------------


def test_serialize_renders_calls_and_results_as_text():
	messages = [
		_user(1, "read it"),
		_assistant(2, "on it", call_ids=["c1"]),
		_result(3, "c1", "data", is_error=True),
	]

	text = serialize_messages(messages)

	assert "<message index=1 role=user>" in text
	assert '- read_file: {"path": "a.txt"}' in text
	assert "role=tool_result name=read_file error=true" in text
	assert serialize_messages([]) == "(no new messages)"


async def test_summarize_returns_the_text():
	mock = MockModel(replies=[AssistantMessage(content="## Goal\nship compaction")])
	plan = plan_all([_user(1, "hello")])
	assert plan is not None

	summary = await summarize(mock, plan, cancellation=None)

	assert summary == "## Goal\nship compaction"


async def test_summarize_raises_on_error_and_empty_replies():
	plan = plan_all([_user(1, "hello")])
	assert plan is not None

	failing = MockModel(replies=[AssistantMessage(stop_reason="error", error_message="boom")])
	with pytest.raises(RuntimeError, match="boom"):
		await summarize(failing, plan, cancellation=None)

	empty = MockModel(replies=[AssistantMessage()])
	with pytest.raises(RuntimeError, match="empty summary"):
		await summarize(empty, plan, cancellation=None)


async def test_compact_events_yields_the_full_protocol():
	messages = [_user(1, "old"), _assistant(2, "answer"), _user(3, "recent")]
	plan = plan_keep_recent(messages, keep_recent_tokens=1)
	assert plan is not None and plan.compact_up_to_seq == 2
	mock = MockModel(replies=[AssistantMessage(content="the summary")])

	events = [
		event
		async for event in compact_events(
			mock,
			plan,
			compaction_reason="threshold",
			cancellation=None,
		)
	]

	assert [event.type for event in events] == ["compaction_started", "compaction", "compaction_ended"]
	row = events[1]
	assert isinstance(row, Compaction)
	assert row.reason == "threshold"
	assert row.summary == "the summary"
	assert row.compact_up_to_seq == 2


def test_serialization_clips_giant_texts():
	giant = "y" * 600_000
	messages = [_user(1, "go"), _assistant(2, "ok", call_ids=["c1"]), _result(3, "c1", giant)]

	text = serialize_messages(messages)

	assert len(text) < 20_000
	assert "more characters truncated]" in text


def test_serialization_budget_drops_oldest_first():
	messages = [_user(i, f"m{i} " + "z" * 4_000) for i in range(1, 6)]

	text = serialize_messages(messages, max_serialized_chars=10_000)

	assert "older messages omitted" in text
	assert "m5" in text and "m4" in text
	assert "m1" not in text


def test_serialization_budget_always_keeps_the_newest_message():
	text = serialize_messages(
		[_user(1, "old stuff"), _user(2, "z" * 4_000)],
		max_serialized_chars=100,
	)

	assert "z" in text
	assert "old stuff" not in text
	assert "older messages omitted" in text


def test_summary_prompt_respects_the_budget():
	plan = plan_all([_user(i, "z" * 4_000) for i in range(1, 30)])
	assert plan is not None

	prompt = build_summary_prompt(plan, max_summary_prompt_tokens=5_000)

	assert estimate_text_tokens(prompt) <= 5_000
	assert "older messages omitted" in prompt


async def test_summarizer_prompt_fits_a_small_window_despite_giant_fields():
	# a 10k-window model, a 24k-char accumulated summary, and 24k chars of manual
	# instructions: every prompt part must be bounded, not just the conversation
	class Recording(MockModel):
		def __init__(self):
			super().__init__(replies=[AssistantMessage(content="bounded summary")], context_window=10_000)
			self.prompt = ""

		async def run(self, request):
			self.prompt = request.messages[0].content
			async for event in super().run(request):
				yield event

	model = Recording()
	messages = [
		compaction_summary_message("s" * 24_000, seq=1),
		_user(2, "keep going"),
		_assistant(3, "done"),
	]
	plan = plan_all(messages)
	assert plan is not None

	summary = await summarize(
		model,
		plan,
		cancellation=None,
		summary_instructions="i" * 24_000,
	)

	assert summary == "bounded summary"
	window = model.context_window
	assert window is not None
	assert estimate_text_tokens(model.prompt) <= calculate_compaction_input_limit(model)
	assert model.prompt.count("[... truncated]") >= 2  # summary and instructions


def test_reserved_output_is_proportional_for_small_windows():
	assert calculate_reserved_output_tokens(128_000) == 16_384
	assert calculate_reserved_output_tokens(10_000) == 2_500
	assert calculate_reserved_output_tokens(1) == 1
