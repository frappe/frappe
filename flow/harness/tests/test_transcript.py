import pytest

from flow_harness.events import (
	ApprovalRequired,
	AssistantMessage,
	Compaction,
	ModelChanged,
	PendingCall,
	Rewind,
	RunEnded,
	RunStarted,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	Usage,
	UserMessage,
	parse_event,
)
from flow_harness.session.log import SessionLog
from flow_harness.session.transcript import COMPACTION_SUMMARY_PREFIX, Transcript, active_path

INTERRUPTED = (
	"Tool call interrupted before its result came back; it may have taken effect. Check before retrying."
)


def make_log(tmp_path, *events) -> SessionLog:
	log = SessionLog(str(tmp_path / "s.jsonl"))
	for event in events:
		log.append(event)
	return log


def test_replay_roundtrip_matches_live_recording(tmp_path):
	events = [
		UserMessage(content="do it"),
		AssistantMessage(
			content=[
				ThinkingContent(
					thinking="plan", thinking_signature="sig", provider_state={"item": {"id": "r1"}}
				),
				TextContent(text="working", provider_state={"id": "msg_1", "phase": "commentary"}),
				ToolCall(
					id="c1", name="bash", arguments={"command": "ls"}, provider_state={"item_id": "fc_1"}
				),
			],
			api="openai-codex-responses",
			provider="codex",
			model="codex/gpt-test",
			response_id="resp_1",
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c1", name="bash", content="file.txt"),
		AssistantMessage(content="done"),
		RunEnded(reason="done"),
	]
	log = make_log(tmp_path, *events)

	transcript = Transcript.replay(log)

	msgs = transcript.messages
	assert isinstance(msgs[0], UserMessage)
	assert isinstance(msgs[1], AssistantMessage)
	assert [block.type for block in msgs[1].content] == ["thinking", "text", "tool_call"]
	# opaque provider round-trip data survives on every block
	assert msgs[1].content[0].provider_state == {"item": {"id": "r1"}}
	assert msgs[1].content[0].thinking_signature == "sig"
	assert msgs[1].content[1].provider_state == {"id": "msg_1", "phase": "commentary"}
	assert msgs[1].tool_calls[0].provider_state == {"item_id": "fc_1"}
	assert msgs[1].response_id == "resp_1"
	assert isinstance(msgs[2], ToolResult)
	assert msgs[2].content == "file.txt"
	assert transcript.pending_approval is None
	assert transcript.missing_results() == ()

	live = Transcript()
	for event in events:  # seqs were assigned by the appends above
		live.record(event)
	assert [m.model_dump() for m in live.messages] == [m.model_dump() for m in msgs]


def test_results_land_in_call_order_and_strays_are_dropped(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={"path": "first.txt"}),
				ToolCall(id="c2", name="read", arguments={"path": "second.txt"}),
				ToolCall(id="c3", name="bash", arguments={}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="read", content="second"),
		ToolResult(tool_call_id="c1", name="read", content="first"),
		ToolResult(tool_call_id="c1", name="read", content="duplicate"),  # the first result wins
		ToolResult(tool_call_id="unknown", name="bash", content="orphan"),  # answers no call
		UserMessage(content="never mind"),  # closes the turn
		ToolResult(tool_call_id="c3", name="bash", content="late"),  # its turn already closed
	)

	messages = Transcript.replay(log).messages

	assert [m.type for m in messages] == ["assistant_message", "tool_result", "tool_result", "user_message"]
	assert [(m.tool_call_id, m.content) for m in messages[1:3]] == [("c1", "first"), ("c2", "second")]


def test_missing_results_close_unanswered_calls_but_spare_the_pause(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="bash", arguments={"command": "ls"}),
				ToolCall(id="c3", name="bash", arguments={"command": "rm x"}),
			],
			stop_reason="tool_use",
		),
		ToolResult(tool_call_id="c2", name="bash", content="done"),
		ApprovalRequired(calls=[PendingCall(id="c3", name="bash", args={"command": "rm x"})]),
		RunEnded(reason="paused"),
	)

	transcript = Transcript.replay(log)
	repairs = transcript.missing_results()

	assert [r.tool_call_id for r in repairs] == ["c1"]
	assert repairs[0].is_error
	assert repairs[0].content == INTERRUPTED
	assert repairs[0].details == {"repair": "interrupted"}
	assert repairs[0].name == "read"
	approval = transcript.pending_approval  # the gated call is the pause, not missing
	assert approval is not None
	assert [c.id for c in approval.calls] == ["c3"]


def test_pending_approval_holds_only_the_open_gated_calls(tmp_path):
	pending = PendingCall(id="c1", name="bash", args={"command": "rm x"})

	def gated_turn():
		return [
			AssistantMessage(
				content=[ToolCall(id="c1", name="bash", arguments={"command": "rm x"})],
				stop_reason="tool_use",
			),
			ApprovalRequired(calls=[pending]),
		]

	cases = {
		"a matching result resolves it": (
			[*gated_turn(), ToolResult(tool_call_id="c1", name="bash", content="approved and ran")],
			None,
		),
		"a new run clears a stale one": ([*gated_turn(), RunStarted(run_id="r2")], None),
		# once a newer turn opens nothing can answer the gated call, so the pause goes with
		# its turn — otherwise a later call reusing that id would silently settle it
		"it does not outlive its turn": (
			[
				*gated_turn(),
				UserMessage(content="do something else"),
				AssistantMessage(
					content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})],
					stop_reason="tool_use",
				),
			],
			None,
		),
		"a reused id scopes to the latest approval": (
			[
				*gated_turn(),
				ToolResult(tool_call_id="c1", name="bash", content="old"),
				RunEnded(reason="done"),
				UserMessage(content="again"),
				*gated_turn(),  # the approval is seq 7
				RunEnded(reason="paused"),
			],
			(7, (pending,)),
		),
		"a free sibling's result does not settle it": (
			[
				AssistantMessage(
					content=[
						ToolCall(id="c1", name="bash", arguments={"command": "rm x"}),
						ToolCall(id="c2", name="read", arguments={"path": "a.txt"}),
					],
					stop_reason="tool_use",
				),
				ToolResult(tool_call_id="c2", name="read", content="contents"),
				ApprovalRequired(calls=[pending]),  # seq 3
				RunEnded(reason="paused"),
			],
			(3, (pending,)),
		),
	}
	for index, (case, (events, expected)) in enumerate(cases.items()):
		approval = Transcript.replay(make_log(tmp_path / str(index), *events)).pending_approval
		assert (None if approval is None else (approval.seq, approval.calls)) == expected, case

	with pytest.raises(ValueError, match="approval event has no preceding assistant tool calls"):
		Transcript.replay(make_log(tmp_path / "orphan", ApprovalRequired(calls=[pending])))


def _texts(transcript):
	return [m.content if isinstance(m, UserMessage) else m.text for m in transcript.messages]


def test_replay_follows_the_branch_that_ends_at_the_leaf(tmp_path):
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
		Rewind(target_seq=1, parent_seq=9),  # 10
		UserMessage(content="C", parent_seq=1),  # 11, a sibling of 2
		Rewind(target_seq=3, parent_seq=11),  # 12, back to the abandoned first branch
		Rewind(target_seq=0, parent_seq=3),  # 13
		UserMessage(content="D", parent_seq=0),  # 14, a new root child
	)

	for leaf, texts, resolved_leaf in (
		(9, ["A", "B", "Y"], 9),  # "X" is off the conversation
		(11, ["C"], 11),  # a rewind to a run's start replaces its user message
		(2, ["A"], 2),  # an explicit leaf previews an earlier point
		(12, ["A", "X"], 3),  # a marker leaf means the branch it moved to
		(13, [], 0),
		(0, [], 0),  # the root, before everything
		(None, ["D"], 14),  # the stored leaf: started over from the root
	):
		transcript = Transcript.replay(log, leaf_seq=leaf)
		assert (_texts(transcript), transcript.leaf_seq) == (texts, resolved_leaf), leaf


def test_active_path_rejects_bad_targets():
	rows = [
		{"seq": 1, "type": "run_started"},
		{"seq": 2, "type": "user_message", "parent_seq": 1},
		{"seq": 3, "type": "rewind", "target_seq": 1, "parent_seq": 2},
	]
	with pytest.raises(ValueError, match="does not exist"):
		active_path(rows, leaf_seq=99)
	with pytest.raises(ValueError, match="does not exist"):
		active_path([], leaf_seq=1)
	cyclic = [{"seq": 1, "type": "rewind", "target_seq": 1}]
	with pytest.raises(ValueError, match="points forward"):
		active_path(cyclic, leaf_seq=1)
	forward = [
		{"seq": 1, "type": "user_message", "parent_seq": 2},
		{"seq": 2, "type": "run_ended", "parent_seq": 1},
	]
	with pytest.raises(ValueError, match="points forward"):
		active_path(forward)


def test_model_changes_fold_per_branch_without_touching_the_conversation(tmp_path):
	log = make_log(
		tmp_path,
		UserMessage(content="A"),  # 1
		AssistantMessage(content="X"),  # 2
		ModelChanged(model="mock/v2"),  # 3
		ModelChanged(model="mock/v3", credential_id="work"),  # 4
	)

	transcript = Transcript.replay(log)

	# the last change on the path wins
	assert (transcript.model, transcript.credential_id) == ("mock/v3", "work")
	assert _texts(transcript) == ["A", "X"]
	assert transcript.leaf_seq == 4  # the next entry hangs off the change
	earlier = Transcript.replay(log, leaf_seq=3)
	assert (earlier.model, earlier.credential_id) == ("mock/v2", None)
	assert Transcript.replay(log, leaf_seq=2).model is None  # back to the session config


def test_compaction_folds_the_prefix_by_seq_into_a_summary(tmp_path):
	log = make_log(
		tmp_path,
		AssistantMessage(
			content=[
				ToolCall(id="c1", name="read", arguments={"path": "a.txt"}),
				ToolCall(id="c2", name="read", arguments={"path": "b.txt"}),
			],
			stop_reason="tool_use",
		),  # 1
		# parallel results arrive out of call order, so list position and seq disagree
		ToolResult(tool_call_id="c2", name="read", content="second"),  # 2, list index 2
		ToolResult(tool_call_id="c1", name="read", content="first"),  # 3, list index 1
		UserMessage(content="B"),  # 4
	)
	live = Transcript.replay(log)
	messages = live.messages  # a running loop reads this exact list

	for event in (
		Compaction(reason="manual", summary="S1", compact_up_to_seq=3),  # 5, drops the whole turn
		AssistantMessage(content="Y"),  # 6
		Usage(input_tokens=900, output_tokens=40),  # 7
		Compaction(reason="threshold", summary="S2", compact_up_to_seq=4),  # 8, supersedes S1
		# the summarizer prompts with the transcript it is compacting; that is not the
		# conversation's new size, which only the next real request reports
		Usage(input_tokens=880, output_tokens=120, standalone=True),  # 9
		UserMessage(content="C"),  # 10
	):
		log.append(event)
		live.record(event)

	assert live.messages is messages
	assert _texts(live) == [COMPACTION_SUMMARY_PREFIX + "S2", "Y", "C"]
	assert live.messages[0].seq == 4  # retained messages stay newer than the compacted boundary
	assert live.context_tokens is None
	assert live.context_message_count == 0
	assert live.leaf_seq == 10
	assert live.missing_results() == ()
	assert [m.model_dump() for m in Transcript.replay(log).messages] == [m.model_dump() for m in messages]
	assert _texts(Transcript.replay(log, leaf_seq=5)) == [COMPACTION_SUMMARY_PREFIX + "S1", "B"]
	# a leaf before the compaction restores the conversation
	assert [m.type for m in Transcript.replay(log, leaf_seq=4).messages] == [
		"assistant_message",
		"tool_result",
		"tool_result",
		"user_message",
	]


def test_a_subagents_rows_advance_the_leaf_but_stay_out_of_the_conversation(tmp_path):
	child = dict(subagent_id="c1")
	log = make_log(
		tmp_path,
		UserMessage(content="go"),
		AssistantMessage(content=[ToolCall(id="c1", name="subagent", arguments={})], stop_reason="tool_use"),
		RunStarted(run_id="run_c1", **child),
		UserMessage(content="count the beans", **child),
		AssistantMessage(content="forty-two", **child),
		RunEnded(reason="done", **child),
		ToolResult(tool_call_id="c1", name="subagent", content="forty-two"),
		AssistantMessage(content="done"),
	)

	session = Transcript.replay(log)
	assert [m.type for m in session.messages] == [
		"user_message",
		"assistant_message",
		"tool_result",
		"assistant_message",
	]
	assert session.leaf_seq == 8  # the child's rows are on the chain
	assert session.subagent_id is None

	child_transcript = Transcript.replay(log, subagent_id="c1")
	assert [m.type for m in child_transcript.messages] == ["user_message", "assistant_message"]
	assert [m.text for m in child_transcript.messages] == ["count the beans", "forty-two"]
	assert child_transcript.leaf_seq == 8
	assert child_transcript.subagent_id == "c1"

	# live recording folds the same way as replay
	live = Transcript()
	for row in active_path(log.read_since(0)):
		live.record(parse_event(row))
	assert [m.model_dump() for m in live.messages] == [m.model_dump() for m in session.messages]
