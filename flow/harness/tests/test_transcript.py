import pytest

from flow.events import (
	ApprovalRequired,
	AssistantMessage,
	ModelChanged,
	PendingCall,
	Rewind,
	RunEnded,
	RunStarted,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow.session.log import SessionLog
from flow.session.transcript import Transcript, active_path

INTERRUPTED = "Tool call interrupted before completion."


def make_log(tmp_path, *events) -> SessionLog:
	log = SessionLog(str(tmp_path / "s.jsonl"))
	for event in events:
		log.append(event)
	return log


def test_replay_roundtrip(tmp_path):
	log = make_log(
		tmp_path,
		UserMessage(content="do it"),
		AssistantMessage(
			content=[
				ThinkingContent(thinking="plan", provider_state={"id": "r1"}),
				TextContent(text="working"),
				ToolCall(id="c1", name="bash", arguments={"command": "ls"}),
			],
			api="openai-codex-responses",
			provider="codex",
			model="codex/gpt-test",
			response_id="resp_1",
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c1", name="bash", content="file.txt"),
	)

	transcript = Transcript.replay(log)

	msgs = transcript.messages
	assert isinstance(msgs[0], UserMessage)
	assert isinstance(msgs[1], AssistantMessage)
	assert [block.type for block in msgs[1].content] == ["thinking", "text", "tool_call"]
	assert msgs[1].content[0].provider_state == {"id": "r1"}
	assert msgs[1].response_id == "resp_1"
	assert isinstance(msgs[2], ToolResult)
	assert msgs[2].content == "file.txt"
	assert transcript.pending_approval is None
	assert transcript.missing_results() == ()


def test_first_result_wins_and_unmatched_results_are_dropped(tmp_path):
	log = make_log(
		tmp_path,
		UserMessage(content="do it"),
		AssistantMessage(content=[ToolCall(id="c1", name="bash", arguments={})], stop_reason="tool_use"),
		ToolResult(tool_call_id="c1", name="bash", content="first"),
		ToolResult(tool_call_id="c1", name="bash", content="second"),
		ToolResult(tool_call_id="unknown", name="bash", content="orphan"),
	)

	transcript = Transcript.replay(log)

	results = [m for m in transcript.messages if isinstance(m, ToolResult)]
	assert [r.content for r in results] == ["first"]
	calls = {c.id for m in transcript.messages if isinstance(m, AssistantMessage) for c in m.tool_calls}
	assert all(r.tool_call_id in calls for r in results)


def test_results_are_ordered_by_call_order_not_arrival(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read_file", arguments={"path": "first.txt"}),
				ToolCall(id="c2", name="read_file", arguments={"path": "second.txt"}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="read_file", content="second result"),
		ToolResult(tool_call_id="c1", name="read_file", content=INTERRUPTED, is_error=True),
	)

	transcript = Transcript.replay(log)

	assert [message.type for message in transcript.messages] == [
		"assistant_message",
		"tool_result",
		"tool_result",
	]
	assert [message.tool_call_id for message in transcript.messages[1:]] == ["c1", "c2"]


def test_missing_results_close_an_interrupted_turn(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="bash", arguments={"command": "ls"}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="bash", content="done"),
	)

	repairs = Transcript.replay(log).missing_results()

	assert [r.tool_call_id for r in repairs] == ["c1"]
	assert repairs[0].is_error
	assert repairs[0].content == INTERRUPTED
	assert repairs[0].details == {"repair": "interrupted"}
	assert repairs[0].name == "read_file"


def test_missing_results_spare_calls_awaiting_approval(tmp_path):
	call = ToolCall(id="c1", name="bash", arguments={"command": "rm x"})
	log = make_log(
		tmp_path,
		AssistantMessage(content=[call], stop_reason="tool_use"),
		ApprovalRequired(calls=[PendingCall(id=call.id, name=call.name, args=call.args)]),
		RunEnded(reason="paused"),
	)

	transcript = Transcript.replay(log)

	assert transcript.missing_results() == ()
	approval = transcript.pending_approval
	assert approval is not None
	assert [c.id for c in approval.calls] == ["c1"]


def test_pending_approval_scopes_reused_tool_ids_to_the_latest_approval(tmp_path):
	call = ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})
	pending = PendingCall(id="c1", name="read_file", args={"path": "a.txt"})
	log = make_log(
		tmp_path,
		AssistantMessage(content=[call], stop_reason="tool_use"),
		ApprovalRequired(calls=[pending]),
		ToolResult(tool_call_id="c1", name="read_file", content="old"),
		RunEnded(reason="done"),
		UserMessage(content="again"),
		AssistantMessage(content=[call], stop_reason="tool_use"),
		ApprovalRequired(calls=[pending]),
		RunEnded(reason="paused"),
	)

	approval = Transcript.replay(log).pending_approval

	assert approval is not None
	assert approval.calls == (pending,)
	assert approval.seq == 7  # the latest approval event, not the answered one


def test_approval_is_resolved_by_matching_results(tmp_path):
	call = ToolCall(id="c1", name="bash", arguments={})
	log = make_log(
		tmp_path,
		AssistantMessage(content=[call], stop_reason="tool_use"),
		ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={})]),
		ToolResult(tool_call_id="c1", name="bash", content="approved and ran"),
	)

	assert Transcript.replay(log).pending_approval is None


def test_run_started_clears_a_stale_approval(tmp_path):
	call = ToolCall(id="c1", name="bash", arguments={})
	log = make_log(
		tmp_path,
		AssistantMessage(content=[call], stop_reason="tool_use"),
		ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={})]),
		RunStarted(run_id="r2"),
	)

	assert Transcript.replay(log).pending_approval is None


def test_a_free_siblings_result_does_not_settle_the_pause(tmp_path):
	"""Only the gated calls hold the pause; the rest of the turn runs and reports."""
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="bash", arguments={"command": "rm x"}),
				ToolCall(id="c2", name="read_file", arguments={"path": "a.txt"}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="read_file", content="contents"),
		ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={"command": "rm x"})]),
		RunEnded(reason="paused"),
	)

	approval = Transcript.replay(log).pending_approval

	assert approval is not None
	assert [c.id for c in approval.calls] == ["c1"]


def test_a_pause_does_not_outlive_the_turn_it_belongs_to(tmp_path):
	"""Once a newer turn opens, nothing can answer the gated call, so the pause goes with
	its turn — otherwise a later call reusing that id would silently settle it."""
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[ToolCall(id="c1", name="bash", arguments={"command": "rm x"})],
			stop_reason="tool_use",
		),
		ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={"command": "rm x"})]),
		UserMessage(content="do something else"),
		AssistantMessage(
			content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})],
			stop_reason="tool_use",
		),
	)

	assert Transcript.replay(log).pending_approval is None


def test_approval_without_preceding_tool_calls_is_rejected(tmp_path):
	log = make_log(tmp_path, ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={})]))

	with pytest.raises(ValueError, match="approval event has no preceding assistant tool calls"):
		Transcript.replay(log)


def test_live_recording_matches_replaying_the_log(tmp_path):
	events = [
		UserMessage(content="go"),
		AssistantMessage(content=[ToolCall(id="c1", name="bash", arguments={})], stop_reason="tool_use"),
		ToolResult(tool_call_id="c1", name="bash", content="ok"),
		AssistantMessage(content="done"),
		RunEnded(reason="done"),
	]
	log = make_log(tmp_path, *events)

	live = Transcript()
	for event in events:  # seqs were assigned by the appends above
		live.record(event)

	assert [m.model_dump() for m in live.messages] == [
		m.model_dump() for m in Transcript.replay(log).messages
	]


def test_result_arriving_after_its_turn_closed_is_dropped(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(content=[ToolCall(id="c1", name="bash", arguments={})], stop_reason="tool_use"),
		UserMessage(content="never mind"),
		ToolResult(tool_call_id="c1", name="bash", content="late"),
	)

	assert [m.type for m in Transcript.replay(log).messages] == ["assistant_message", "user_message"]


def test_replay_spans_runs_with_a_repair_and_a_reused_call_id(tmp_path):
	"""A crashed run whose repair was persisted at the next load, then a second run
	reusing the same call id and pausing for approval."""
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),
		UserMessage(content="read two files"),
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="read_file", arguments={"path": "b.txt"}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="read_file", content="b"),
		# the run was interrupted here; the repair is appended before any new entry
		ToolResult(
			tool_call_id="c1",
			name="read_file",
			content=INTERRUPTED,
			is_error=True,
			details={"repair": "interrupted"},
		),
		RunStarted(run_id="run_2"),
		UserMessage(content="now delete one"),
		AssistantMessage(
			content=[ToolCall(id="c1", name="bash", arguments={"command": "rm a.txt"})],
			stop_reason="tool_use",
		),
		ApprovalRequired(calls=[PendingCall(id="c1", name="bash", args={"command": "rm a.txt"})]),
		RunEnded(reason="paused"),
	)

	transcript = Transcript.replay(log)

	assert [m.type for m in transcript.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"tool_result",
		"user_message",
		"assistant_message",
	]
	# the late repair still lands beside its own batch, in call order
	assert [m.tool_call_id for m in transcript.messages[2:4]] == ["c1", "c2"]
	# the reused id neither resolves the new approval nor counts as missing
	approval = transcript.pending_approval
	assert approval is not None
	assert [c.id for c in approval.calls] == ["c1"]
	assert transcript.missing_results() == ()


def test_replay_follows_the_active_branch_after_a_rewind(tmp_path):
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),  # 1
		UserMessage(content="A"),  # 2
		AssistantMessage(content="X"),  # 3
		RunEnded(),  # 4
		Rewind(target_seq=2),  # 5
		RunStarted(run_id="run_2", parent_seq=2),  # 6, branches off 2
		UserMessage(content="B", parent_seq=6),  # 7
		AssistantMessage(content="Y", parent_seq=7),  # 8
		RunEnded(parent_seq=8),  # 9
	)

	transcript = Transcript.replay(log)

	# "X" is off the conversation
	assert [
		(m.type, getattr(m, "text", None) or getattr(m, "content", None)) for m in transcript.messages
	] == [
		("user_message", "A"),
		("user_message", "B"),
		("assistant_message", "Y"),
	]
	assert transcript.leaf_seq == 9


def test_rewind_to_a_runs_start_replaces_the_user_message(tmp_path):
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),  # 1
		UserMessage(content="A"),  # 2
		AssistantMessage(content="X"),  # 3
		RunEnded(),  # 4
		Rewind(target_seq=1),  # 5
		UserMessage(content="B", parent_seq=1),  # 6, sibling of 2
		AssistantMessage(content="Y", parent_seq=6),  # 7
	)

	transcript = Transcript.replay(log)

	assert [getattr(m, "text", None) or m.content for m in transcript.messages] == ["B", "Y"]


def test_explicit_leaf_previews_an_earlier_point(tmp_path):
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),  # 1
		UserMessage(content="A"),  # 2
		AssistantMessage(content="X"),  # 3
		RunEnded(),  # 4
	)

	preview = Transcript.replay(log, leaf_seq=2)

	assert [m.content for m in preview.messages] == ["A"]
	assert preview.leaf_seq == 2


def test_a_later_rewind_switches_back_to_an_abandoned_branch(tmp_path):
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),  # 1
		UserMessage(content="A"),  # 2
		AssistantMessage(content="X"),  # 3
		Rewind(target_seq=1),  # 4
		UserMessage(content="B", parent_seq=1),  # 5
		Rewind(target_seq=3, parent_seq=5),  # 6, back to the first branch
	)

	transcript = Transcript.replay(log)

	assert [getattr(m, "text", None) or m.content for m in transcript.messages] == ["A", "X"]
	assert transcript.leaf_seq == 3


def test_active_path_rejects_bad_targets():
	rows = [
		{"seq": 1, "type": "run_started"},
		{"seq": 2, "type": "user_message", "parent_seq": 1},
		{"seq": 3, "type": "rewind", "target_seq": 1, "parent_seq": 2},
	]
	with pytest.raises(ValueError, match="does not exist"):
		active_path(rows, leaf_seq=99)
	with pytest.raises(ValueError, match="rewind marker"):
		active_path(rows, leaf_seq=3)
	with pytest.raises(ValueError, match="does not exist"):
		active_path([], leaf_seq=1)
	forward = [
		{"seq": 1, "type": "user_message", "parent_seq": 2},
		{"seq": 2, "type": "run_ended", "parent_seq": 1},
	]
	with pytest.raises(ValueError, match="points forward"):
		active_path(forward)


def test_rewind_to_the_root_starts_over(tmp_path):
	log = make_log(
		tmp_path,
		RunStarted(run_id="run_1"),  # 1
		UserMessage(content="A"),  # 2
		AssistantMessage(content="X"),  # 3
		RunEnded(),  # 4
		Rewind(target_seq=0),  # 5
		UserMessage(content="B", parent_seq=0),  # 6, a new root child
	)

	assert Transcript.replay(log, leaf_seq=0).messages == []
	transcript = Transcript.replay(log)
	assert [m.content for m in transcript.messages] == ["B"]
	assert transcript.leaf_seq == 6


def test_model_change_folds_without_touching_the_conversation(tmp_path):
	log = make_log(
		tmp_path,
		UserMessage(content="A"),  # 1
		AssistantMessage(content="X"),  # 2
		ModelChanged(model="mock/v2", credential_id="work"),  # 3
	)

	transcript = Transcript.replay(log)

	assert (transcript.model, transcript.credential_id) == ("mock/v2", "work")
	assert [getattr(m, "text", None) or m.content for m in transcript.messages] == ["A", "X"]
	assert transcript.leaf_seq == 3  # the next entry hangs off the change


def test_replay_to_before_a_model_change_forgets_it(tmp_path):
	log = make_log(
		tmp_path,
		UserMessage(content="A"),  # 1
		ModelChanged(model="mock/v2"),  # 2
		ModelChanged(model="mock/v3", credential_id="work"),  # 3
	)

	assert Transcript.replay(log).model == "mock/v3"  # the last change on the path wins
	earlier = Transcript.replay(log, leaf_seq=2)
	assert (earlier.model, earlier.credential_id) == ("mock/v2", None)
	assert Transcript.replay(log, leaf_seq=1).model is None  # back to the session config
