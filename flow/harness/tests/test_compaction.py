"""Compaction planning and summarization: deterministic estimation, turn-safe
boundaries, prompt selection, and the summarizer's silent tool-less model call."""

import json

import pytest

from flow_harness.agent.compaction import (
	ESTIMATED_IMAGE_TOKENS,
	KEEP_RECENT_TOKENS,
	MESSAGE_OVERHEAD_TOKENS,
	TOOL_OVERHEAD_TOKENS,
	build_summary_prompt,
	calculate_compaction_input_limit,
	calculate_reserved_output_tokens,
	compact_events,
	estimate_context_tokens,
	estimate_message_tokens,
	estimate_text_tokens,
	plan_all,
	plan_keep_recent,
	serialize_messages,
	summarize,
)
from flow_harness.events import (
	AssistantMessage,
	AttachmentContent,
	Compaction,
	TextContent,
	ToolCall,
	ToolResult,
	Usage,
	UserMessage,
)
from flow_harness.model.mock import MockModel
from flow_harness.session.transcript import compaction_summary_message

BIG = "x" * (KEEP_RECENT_TOKENS * 4)  # one message that alone overflows the kept tail


def _user(seq, content):
	return UserMessage(seq=seq, content=content)


def _assistant(seq, text="", call_ids=()):
	content = [TextContent(text=text)] if text else []
	content += [ToolCall(id=cid, name="read", arguments={"path": "a.txt"}) for cid in call_ids]
	return AssistantMessage(seq=seq, content=content, stop_reason="tool_use" if call_ids else "stop")


def _result(seq, call_id, content, is_error=False):
	return ToolResult(seq=seq, tool_call_id=call_id, name="read", content=content, is_error=is_error)


class _RecordingModel(MockModel):
	"""Keeps the last request it served."""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.request = None

	async def run(self, request):
		self.request = request
		async for event in super().run(request):
			yield event


# --- estimation -------------------------------------------------------------


def test_estimates_and_the_output_reserve():
	# text is chars over four, rounded up
	assert estimate_text_tokens("") == 0
	assert estimate_text_tokens("abcd") == 1
	assert estimate_text_tokens("abcde") == 2

	# a request counts its system prompt, tools and messages
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

	# a tool result's images count; a file counts only its note
	image = AttachmentContent(id="a" * 24, name="shot.png", mime_type="image/png", size=3, kind="image")
	plain = ToolResult(tool_call_id="c1", name="read", content="[Image: shot.png]")
	with_image = plain.model_copy(update={"attachments": [image]})
	assert estimate_message_tokens(with_image) == estimate_message_tokens(plain) + ESTIMATED_IMAGE_TOKENS
	video = AttachmentContent(
		id="a" * 24,
		name="clip.mp4",
		mime_type="video/mp4",
		size=50_000_000,
		kind="file",
		path="/data/clip.mp4",
	)
	assert estimate_message_tokens(UserMessage(content=[TextContent(text="what happens here?"), video])) < 100

	# the output reserve is proportional for small windows
	assert calculate_reserved_output_tokens(128_000) == 16_384
	assert calculate_reserved_output_tokens(10_000) == 2_500
	assert calculate_reserved_output_tokens(1) == 1


# --- planning ---------------------------------------------------------------


def test_keep_recent_cuts_where_a_turn_starts_the_kept_tail():
	cases = [
		# case, messages, (compact_up_to_seq, summarized seqs, previous summary) or None
		("empty", [], None),
		("one message", [_user(1, "hi")], None),
		("fits inside the kept tail", [_user(1, "hi"), _assistant(2, "yo")], None),
		(
			"a single turn cannot be split",
			[_user(1, BIG), _assistant(2, call_ids=["c1"]), _result(3, "c1", "data")],
			None,
		),
		(
			"cut at the user turn that starts the kept tail",
			[
				_user(1, BIG),
				_assistant(2, "first answer"),
				_user(3, "second question"),
				_assistant(4, "second answer"),
			],
			(2, [1, 2], None),
		),
		(
			# a big tool result: the cut snaps past it to the next assistant start
			"never on a tool result",
			[
				_user(1, "start"),
				_assistant(2, "working", call_ids=["c1"]),
				_result(3, "c1", BIG),
				_assistant(4, "final"),
			],
			(3, [1, 2, 3], None),
		),
	]
	for name, messages, expected in cases:
		plan = plan_keep_recent(messages)
		got = plan and (
			plan.compact_up_to_seq,
			[m.seq for m in plan.messages_to_summarize],
			plan.previous_summary,
		)
		assert got == expected, name


def test_plan_all_takes_everything_durable_and_picks_the_prompt():
	assert plan_all([]) is None
	assert plan_all([UserMessage(content="never committed")]) is None  # no seq, no boundary

	plan = plan_all([_user(1, "a"), _assistant(2, "b")])
	assert plan is not None
	assert plan.compact_up_to_seq == 2
	assert len(plan.messages_to_summarize) == 2
	prompt = build_summary_prompt(plan, summary_instructions="focus on tests")
	assert "<previous-summary>" not in prompt
	assert "context checkpoint summary" in prompt
	assert prompt.endswith("Additional focus: focus on tests")

	# a previous summary is split off for the update prompt
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


# --- serialization + summarizer --------------------------------------------


def test_serialize_renders_text_and_stays_within_its_budget():
	messages = [
		_user(1, "read it"),
		_assistant(2, "on it", call_ids=["c1"]),
		_result(3, "c1", "data", is_error=True),
	]

	text = serialize_messages(messages)

	assert "<message index=1 role=user>" in text
	assert '- read: {"path": "a.txt"}' in text
	assert "role=tool_result name=read error=true" in text
	assert serialize_messages([]) == "(no new messages)"

	attachment = AttachmentContent(
		id="a" * 24, name="notes.txt", mime_type="text/plain", size=12, kind="text"
	)
	message = UserMessage(seq=1, content=[TextContent(text="review"), attachment])
	text = serialize_messages([message], resolve_attachment=lambda _: b"secret notes")
	assert '<file name="notes.txt">\nsecret notes\n</file>' in text

	# giant tool output is clipped; over budget, the oldest messages go first
	giant = "y" * 600_000
	text = serialize_messages([_user(1, "go"), _assistant(2, "ok", call_ids=["c1"]), _result(3, "c1", giant)])
	assert len(text) < 20_000
	assert "more characters truncated]" in text

	text = serialize_messages(
		[_user(i, f"m{i} " + "z" * 4_000) for i in range(1, 6)], max_serialized_chars=10_000
	)
	assert "older messages omitted" in text
	assert "m5" in text and "m4" in text
	assert "m1" not in text

	# the newest message always stays, even alone over the budget
	text = serialize_messages([_user(1, "old stuff"), _user(2, "z" * 4_000)], max_serialized_chars=100)
	assert "z" in text
	assert "old stuff" not in text
	assert "older messages omitted" in text


async def test_the_summary_prompt_fits_its_budget():
	plan = plan_all([_user(i, "z" * 4_000) for i in range(1, 30)])
	assert plan is not None
	prompt = build_summary_prompt(plan, max_summary_prompt_tokens=5_000)
	assert estimate_text_tokens(prompt) <= 5_000
	assert "older messages omitted" in prompt

	# a 10k-window model, a 24k-char accumulated summary, and 24k chars of manual
	# instructions: every prompt part must be bounded, not just the conversation
	model = _RecordingModel(replies=[AssistantMessage(content="bounded summary")], context_window=10_000)
	messages = [
		compaction_summary_message("s" * 24_000, seq=1),
		_user(2, "keep going"),
		_assistant(3, "done"),
	]
	plan = plan_all(messages)
	assert plan is not None

	summary, _usage = await summarize(model, plan, cancellation=None, summary_instructions="i" * 24_000)

	assert summary == "bounded summary"
	prompt = model.request.messages[0].content
	assert estimate_text_tokens(prompt) <= calculate_compaction_input_limit(model)
	assert prompt.count("[... truncated]") >= 2  # summary and instructions


async def test_summarize_makes_a_text_only_call_and_returns_its_text():
	attachment = AttachmentContent(
		id="b" * 24,
		name="screen.png",
		mime_type="image/png",
		size=3,
		kind="image",
		width=1,
		height=1,
	)
	plan = plan_all([UserMessage(seq=1, content=[attachment])])
	assert plan is not None
	model = _RecordingModel(replies=[AssistantMessage(content="## Goal\nship compaction")])

	summary, usage = await summarize(model, plan, cancellation=None, resolve_attachment=lambda _: b"png")

	assert summary == "## Goal\nship compaction"
	# a call of its own: its tokens are spend, not the conversation's size
	assert usage is not None and usage.output_tokens > 0 and usage.standalone
	# images reach the summarizer as text only
	assert model.request.messages[0].attachments == ()
	assert "[Attached image: screen.png]" in model.request.messages[0].text
	assert model.request.resolve_attachment is None

	for reply, error in (
		(AssistantMessage(stop_reason="error", error_message="boom"), "boom"),
		(AssistantMessage(), "empty summary"),
	):
		with pytest.raises(RuntimeError, match=error):
			await summarize(MockModel(replies=[reply]), plan, cancellation=None)


async def test_compact_events_log_the_row_and_its_spend_even_when_the_summary_fails():
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

	# the summarizer's own call is logged too, after the row it paid for
	assert [event.type for event in events] == [
		"compaction_started",
		"compaction",
		"usage",
		"compaction_ended",
	]
	row = events[1]
	assert isinstance(row, Compaction)
	assert row.reason == "threshold"
	assert row.summary == "the summary"
	assert row.compact_up_to_seq == 2
	spend = events[2]
	assert isinstance(spend, Usage)
	assert spend.standalone and spend.input_tokens > 0

	failing = MockModel(replies=[AssistantMessage(stop_reason="error", error_message="boom")])
	events = []
	with pytest.raises(RuntimeError, match="boom"):
		async for event in compact_events(failing, plan, compaction_reason="threshold", cancellation=None):
			events.append(event)

	# a provider still charges for a call that failed
	assert [event.type for event in events] == ["compaction_started", "usage", "compaction_ended"]
	assert isinstance(events[1], Usage) and events[1].standalone
	assert events[2].error_message == "boom"
