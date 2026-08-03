"""Phase 4 client core: the ConversationState reducer (pure, no I/O)."""

from flow.events import (
	ApprovalRequired,
	AssistantMessage,
	ModelChanged,
	PendingCall,
	Retry,
	Rewind,
	RunEnded,
	RunError,
	RunStarted,
	TextContent,
	TextDelta,
	ThinkingDelta,
	ToolCall,
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


def _apply_all(state: State, events) -> None:
	for event in events:
		state.apply(event)


def test_deltas_accumulate_and_durable_message_replaces_them():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(UserMessage(content="hi", seq=2))

	assert state.apply(ThinkingDelta(thinking="hmm ")) == [StreamDelta(ThinkingDelta(thinking="hmm "))]
	state.apply(ThinkingDelta(thinking="ok"))
	state.apply(TextDelta(text="Hel"))
	state.apply(TextDelta(text="lo"))
	state.apply(ToolCallStarted(id="c1", name="bash"))
	state.apply(TextDelta(text="tail"))

	# consecutive same-kind deltas merge; a kind switch starts a new part
	assert state.partial == [
		PartialThinking("hmm ok"),
		PartialText("Hello"),
		PartialToolCall(id="c1", name="bash"),
		PartialText("tail"),
	]

	durable = AssistantMessage(content="Hello", seq=3)
	assert state.apply(durable) == [EntryReplaced(durable)]
	assert state.partial == []
	assert state.entries == [UserMessage(content="hi", seq=2), durable]


def test_assistant_message_without_preview_is_an_entry_added():
	state = State()
	message = AssistantMessage(content="hi", seq=1)
	assert state.apply(message) == [EntryAdded(message)]


def test_retry_started_discards_the_preview():
	state = State()
	state.apply(TextDelta(text="half a rep"))
	assert state.partial

	changes = state.apply(Retry(status="started", attempt=2, max_attempts=5))
	assert changes == [PartialCleared(), StatusChanged()]
	assert state.partial == []
	assert state.retry is not None and state.retry.attempt == 2

	# retry progress without a new attempt does not clear anything
	state.apply(TextDelta(text="fresh"))
	state.apply(Retry(status="scheduled", attempt=3, delay_seconds=2.0))
	assert state.partial == [PartialText("fresh")]

	# the durable message means the attempt succeeded
	state.apply(AssistantMessage(content="done", seq=1))
	assert state.retry is None


def test_approval_lifecycle_settled_by_matching_results():
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


def test_approval_cleared_by_run_started_and_terminal_run_ended():
	state = State()
	calls = [PendingCall(id="c1", name="bash", args={}, prompt="?")]

	state.apply(ApprovalRequired(calls=calls, seq=3))
	changes = state.apply(RunStarted(run_id="r2", seq=4))
	assert changes == [ApprovalChanged(), StatusChanged()]
	assert state.pending_approval is None
	assert state.running

	state.apply(ApprovalRequired(calls=calls, seq=5))
	state.apply(RunEnded(reason="aborted", seq=6))
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


def test_rewind_drops_preview_and_pending_approval():
	state = State()
	state.apply(TextDelta(text="stream"))
	state.apply(ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={}, prompt="?")], seq=2))

	changes = state.apply(Rewind(target_seq=0, seq=3))
	assert changes == [PartialCleared(), ApprovalChanged(), EntriesTruncated(0), StatusChanged()]
	assert state.partial == []
	assert state.pending_approval is None
	assert state.entries == []


def test_usage_accumulates_across_runs():
	state = State()
	state.apply(Usage(input_tokens=100, output_tokens=20, cost=0.01, seq=1))
	state.apply(Usage(input_tokens=50, output_tokens=5, cost=0.005, seq=2))
	assert state.input_tokens == 150
	assert state.output_tokens == 25
	assert state.cost == 0.015


def test_run_error_and_run_started_lifecycle():
	state = State()
	error = RunError(message="boom", kind="overloaded", seq=2)
	assert state.apply(error) == [StatusChanged()]
	assert state.last_error is error
	state.apply(Retry(status="exhausted", attempt=5))
	state.apply(RunEnded(reason="error", seq=3))
	assert not state.running
	assert state.retry is None  # retry progress is per-run
	assert state.last_error is error  # the banner stays visible while idle

	state.apply(RunStarted(run_id="r2", seq=4))
	assert state.running
	assert state.last_error is None


def test_steering_appends_mid_run_without_touching_the_preview():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(UserMessage(content="first", seq=2))
	state.apply(TextDelta(text="strea"))

	steered = UserMessage(content="actually, stop", seq=3)
	assert state.apply(steered) == [EntryAdded(steered)]
	assert state.running
	assert state.partial == [PartialText("strea")]
	assert state.entries[-1] is steered


def test_run_ended_clears_a_leftover_preview():
	state = State()
	state.apply(RunStarted(run_id="r1", seq=1))
	state.apply(TextDelta(text="orphan"))
	changes = state.apply(RunEnded(reason="aborted", seq=2))
	assert changes == [PartialCleared(), StatusChanged()]
	assert state.partial == []


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
			"config": {"model": "mock", "credential_id": None, "reasoning_effort": None},
		}
	)
	assert state.running
	assert state.latest_seq == 42
	assert state.model == "openai/gpt"
	assert state.credential_id == "work"
	assert state.reasoning_effort == "high"

	# a model change then a rewind over it falls back to the session config, not
	# the folded value the seed reported
	state.apply(ModelChanged(model="xai/grok", seq=43))
	state.apply(Rewind(target_seq=42, seq=44))
	assert state.model == "mock"
	assert state.credential_id is None
	assert state.reasoning_effort is None


def test_latest_seq_tracks_durable_events_only():
	state = State()
	state.apply(UserMessage(content="hi", seq=7))
	state.apply(TextDelta(text="live"))
	assert state.latest_seq == 7


def test_replaying_history_matches_live_folding():
	"""Seeding + replaying `GET /entries` rows lands in the same state as watching live."""
	events = [
		RunStarted(run_id="r1", seq=1),
		UserMessage(content="hi", seq=2),
		AssistantMessage(
			content=[TextContent(text="ok"), ToolCall(id="c1", name="bash", arguments={"cmd": "ls"})],
			seq=3,
		),
		ToolResult(tool_call_id="c1", name="bash", content="files", seq=4),
		Usage(input_tokens=10, output_tokens=2, cost=0.001, seq=5),
		RunEnded(reason="done", seq=6),
	]
	live, replayed = State(), State()
	_apply_all(live, events)
	_apply_all(replayed, events)
	assert replayed.entries == live.entries
	assert replayed.latest_seq == live.latest_seq == 6
	assert not replayed.running
	assert replayed.input_tokens == 10
