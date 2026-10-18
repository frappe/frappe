"""Phase 4 client core: the ConversationState reducer (pure, no I/O)."""

from flow_harness.events import (
	ApprovalRequired,
	AssistantMessage,
	DisplaySegment,
	ModelChanged,
	PendingCall,
	PreviewReplayStarted,
	Retry,
	Rewind,
	RunEnded,
	RunError,
	RunStarted,
	TextContent,
	TextDelta,
	ThinkingDelta,
	ToolCallDisplayReady,
	ToolCallStarted,
	ToolResult,
	Usage,
	UserMessage,
)
from flow_tui.client.state import (
	ApprovalChanged,
	EntriesTruncated,
	EntryAdded,
	EntryReplaced,
	PartialCleared,
	PartialText,
	PartialThinking,
	PartialToolCall,
	StatusChanged,
	StreamDelta,
)
from flow_tui.client.state import (
	ConversationState as State,
)


def test_deltas_accumulate_and_durable_message_replaces_them():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(UserMessage(content="hi", seq=2))

	assert state.apply(ThinkingDelta(thinking="hmm ")) == [StreamDelta(ThinkingDelta(thinking="hmm "))]
	state.apply(ThinkingDelta(thinking="ok"))
	state.apply(TextDelta(text="Hel"))
	state.apply(TextDelta(text="lo"))
	state.apply(ToolCallStarted(id="c1", name="bash"))
	state.apply(
		ToolCallDisplayReady(
			id="c1",
			name="bash",
			arguments={"command": "pwd"},
			display="Running pwd",
		)
	)
	state.apply(TextDelta(text="tail"))

	# consecutive same-kind deltas merge; a kind switch starts a new part
	preview = [
		PartialThinking("hmm ok"),
		PartialText("Hello"),
		PartialToolCall(
			id="c1",
			name="bash",
			arguments={"command": "pwd"},
			display=[DisplaySegment(text="Running pwd")],
		),
		PartialText("tail"),
	]
	assert state.partial == preview

	# a steering message lands mid-run without touching the preview
	steered = UserMessage(content="actually, stop", seq=3)
	assert state.apply(steered) == [EntryAdded(steered)]
	assert state.running
	assert state.partial == preview
	assert state.entries[-1] is steered

	durable = AssistantMessage(content="Hello", seq=4)
	assert state.apply(durable) == [EntryReplaced(durable)]
	assert state.partial == []
	assert state.entries == [UserMessage(content="hi", seq=2), steered, durable]

	# without a preview the durable message is a plain append
	message = AssistantMessage(content="hi", seq=5)
	assert state.apply(message) == [EntryAdded(message)]


def test_retry_and_preview_replay_discard_the_preview():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(TextDelta(text="prefix"))

	# a replayed preview replaces the existing provisional one
	assert state.apply(PreviewReplayStarted()) == [PartialCleared()]
	state.apply(TextDelta(text="prefix"))
	state.apply(TextDelta(text=" suffix"))
	assert state.partial == [PartialText("prefix suffix")]

	changes = state.apply(Retry(status="started", attempt=2, max_attempts=5))
	assert changes == [PartialCleared(), StatusChanged()]
	assert state.partial == []
	assert state.retry is not None and state.retry.attempt == 2

	# retry progress without a new attempt does not clear anything
	state.apply(TextDelta(text="fresh"))
	state.apply(Retry(status="scheduled", attempt=3, delay_seconds=2.0))
	assert state.partial == [PartialText("fresh")]

	# the durable message means the attempt succeeded
	state.apply(AssistantMessage(content="done", seq=2))
	assert state.retry is None


def test_approval_lifecycle():
	state = State()
	calls = [
		PendingCall(id="c1", name="bash", args={"cmd": "rm x"}, prompt="Run rm x?"),
		PendingCall(id="c2", name="bash", args={"cmd": "rm y"}, prompt="Run rm y?"),
	]
	changes = state.apply(ApprovalRequired(calls=calls, seq=5))
	assert changes == [ApprovalChanged()]
	assert state.pending_approval is not None
	assert state.pending_approval.seq == 5
	state.apply(RunEnded(reason="paused", seq=6))
	assert state.pending_approval is not None  # a pause outlives its run
	assert not state.running

	# a result for an unrelated call leaves the batch alone
	stray = ToolResult(tool_call_id="other", name="bash", content="ok", seq=7)
	assert state.apply(stray) == [EntryAdded(stray)]
	assert len(state.pending_approval.calls) == 2

	first = ToolResult(tool_call_id="c1", name="bash", content="ok", seq=8)
	assert state.apply(first) == [EntryAdded(first), ApprovalChanged()]
	assert [call.id for call in state.pending_approval.calls] == ["c2"]

	second = ToolResult(tool_call_id="c2", name="bash", content="ok", seq=9)
	state.apply(second)
	assert state.pending_approval is None

	# a new run or a terminal run end also clears it
	state.apply(ApprovalRequired(calls=calls[:1], seq=10))
	changes = state.apply(RunStarted(run_id="r2", seq=11))
	assert changes == [ApprovalChanged(), StatusChanged()]
	assert state.pending_approval is None
	assert state.running

	state.apply(ApprovalRequired(calls=calls[:1], seq=12))
	state.apply(RunEnded(reason="aborted", seq=13))
	assert state.pending_approval is None


def test_rewind_truncates_entries_and_refolds_model():
	state = State()
	state.seed(
		{
			"model": "mock",
			"credential_id": None,
			"reasoning_effort": None,
			"running": False,
			"latest_seq": 0,
			"config": {"model": "mock", "credential_id": None, "reasoning_effort": None},
		}
	)

	state.apply(UserMessage(content="one", seq=1))
	state.apply(AssistantMessage(content="a1", seq=2))
	state.apply(ModelChanged(model="anthropic/claude", reasoning_effort="high", seq=3))
	state.apply(UserMessage(content="two", seq=4))
	state.apply(AssistantMessage(content="a2", seq=5))
	state.apply(ModelChanged(model="openai/gpt", reasoning_effort="low", seq=6))
	assert state.model == "openai/gpt"

	# rewind past the second model change: the first one is folded again
	changes = state.apply(Rewind(target_seq=4, seq=7))
	assert changes == [EntriesTruncated(4), StatusChanged()]
	assert [entry.seq for entry in state.entries] == [1, 2, 4]
	assert state.model == "anthropic/claude"
	assert state.reasoning_effort == "high"

	# rewind past every model change: back to the seeded session config
	state.apply(Rewind(target_seq=2, seq=8))
	assert [entry.seq for entry in state.entries] == [1, 2]
	assert state.model == "mock"
	assert state.reasoning_effort is None

	# a rewind also drops the preview and a pending approval
	state.apply(TextDelta(text="stream"))
	state.apply(ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={}, prompt="?")], seq=9))
	changes = state.apply(Rewind(target_seq=0, seq=10))
	assert changes == [PartialCleared(), ApprovalChanged(), EntriesTruncated(0), StatusChanged()]
	assert state.partial == []
	assert state.pending_approval is None
	assert state.entries == []


def test_run_lifecycle_and_usage_totals():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(
		Usage(
			input_tokens=100,
			output_tokens=20,
			cache_read_tokens=80,
			cache_write_tokens=10,
			cost=0.01,
			seq=2,
		)
	)
	state.apply(TextDelta(text="orphan"))
	error = RunError(message="boom", kind="overloaded", seq=3)
	assert state.apply(error) == [StatusChanged()]
	assert state.last_error is error
	state.apply(Retry(status="exhausted", attempt=5))

	# the run's end drops a leftover preview
	assert state.apply(RunEnded(reason="error", seq=4)) == [PartialCleared(), StatusChanged()]
	assert state.partial == []
	assert not state.running
	assert state.retry is None  # retry progress is per-run
	assert state.last_error is error  # the banner stays visible while idle

	state.apply(RunStarted(run_id="r2", seq=5))
	assert state.running
	assert state.last_error is None

	# usage accumulates across runs
	state.apply(
		Usage(
			input_tokens=50,
			output_tokens=5,
			cache_read_tokens=30,
			cache_write_tokens=5,
			cost=0.005,
			seq=6,
		)
	)
	assert state.input_tokens == 150
	assert state.output_tokens == 25
	assert state.cache_read_tokens == 110
	assert state.cache_write_tokens == 15
	assert state.cost == 0.015


def test_seed_from_session_info():
	state = State()
	state.seed(
		{
			"session_id": "s1",
			"state": "running",
			"running": True,
			"latest_seq": 42,
			"model": "openai/gpt",
			"credential_id": "work",
			"reasoning_effort": "high",
			"config": {"model": "mock", "credential_id": None, "reasoning_effort": None, "cwd": "/work"},
		}
	)
	assert state.running
	assert state.latest_seq == 42
	assert state.model == "openai/gpt"
	assert state.credential_id == "work"
	assert state.reasoning_effort == "high"
	assert state.cwd == "/work"

	# a model change then a rewind over it falls back to the session config, not
	# the folded value the seed reported
	state.apply(ModelChanged(model="xai/grok", seq=43))
	state.apply(Rewind(target_seq=42, seq=44))
	assert state.model == "mock"
	assert state.credential_id is None
	assert state.reasoning_effort is None


def test_a_sub_agents_rows_join_the_transcript_and_its_usage_the_totals():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(RunStarted(run_id="r2", seq=2, subagent_id="c1"))
	state.apply(UserMessage(content="count", seq=3, subagent_id="c1"))
	assert state.apply(TextDelta(text="forty", subagent_id="c1")) == []
	assert state.partial == []  # the child's preview is not the session's

	message = AssistantMessage(content=[TextContent(text="forty-two")], seq=4, subagent_id="c1")
	assert state.apply(message) == [EntryAdded(message)]
	result = ToolResult(tool_call_id="c2", name="bash", content="42", seq=5, subagent_id="c1")
	assert state.apply(result) == [EntryAdded(result)]
	assert state.entries == [message, result]

	calls = (PendingCall(id="c3", name="bash", args={"command": "rm x"}),)
	assert state.apply(ApprovalRequired(calls=list(calls), seq=6, subagent_id="c1")) == []
	assert state.pending_approval is None  # a child's pause is never the session's
	assert state.apply(Usage(input_tokens=30, output_tokens=9, cost=0.5, seq=7, subagent_id="c1")) == [
		StatusChanged()
	]
	assert (state.input_tokens, state.output_tokens, state.cost) == (30, 9, 0.5)
	assert state.context_tokens == 0  # its context is not
	assert state.apply(RunEnded(reason="done", seq=8, subagent_id="c1")) == []
	assert state.running is True
	assert state.latest_seq == 8
