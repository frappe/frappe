"""Turns the event log into the state a session needs while it runs.

State is maintained in real time: the session calls `record` on each event as it is
committed, so nothing here ever re-reads the log mid-run. Reading the whole log happens
exactly once, at load — `replay` rebuilds a transcript by pushing every logged event
through that same `record`, so a restarted session and a live one always agree.

It keeps four things current:
  - `messages`: the conversation in the shape a provider accepts, with each tool
    result placed right after the call it answers.
  - the open tool calls: the newest assistant message whose tool calls have not all
    come back yet. Incoming results are matched against them.
  - `pending_approval`: the calls a paused run is waiting for a human to decide.
  - the latest provider-reported context size and the message boundary it covered,
    so the next operation can account for trailing messages without guessing.

A result is matched against whichever tool calls are open when it arrives. So the
stand-in results that close an interrupted turn (`missing_results`) have to reach the
log before any newer message does; the session writes them when it settles a failed
run, and at load for a run a dead process never settled.

A sub-agent's rows share the log, tagged with its id. A transcript folds only the rows
of the agent it belongs to; every other row just advances the leaf.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from flow_harness.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	Compaction,
	ModelChanged,
	PendingCall,
	ReasoningEffort,
	Rewind,
	RunEnded,
	RunStarted,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
	parse_event,
)
from flow_harness.session.log import SessionLog

_INTERRUPTED_TOOL_CONTENT = (
	"Tool call interrupted before its result came back; it may have taken effect. Check before retrying."
)
COMPACTION_SUMMARY_PREFIX = "Previous conversation summary:\n"
_logger = logging.getLogger(__name__)


def compaction_summary_message(summary: str, *, seq: int | None = None) -> UserMessage:
	"""The synthetic message a compaction folds to; never persisted. Its sequence is
	the compacted boundary so retained messages remain newer than the summary."""
	return UserMessage(content=COMPACTION_SUMMARY_PREFIX + summary, seq=seq)


def active_path(rows: list[dict], leaf_seq: int | None = None) -> list[dict]:
	"""Root→leaf rows of the branch ending at `leaf_seq` (default: the stored leaf).

	Leaf 0 is the empty root — the branch point before everything. Rows off the
	branch stay in the log but are not part of the conversation.

	A rewind marker is not a conversation entry, so naming one means the branch it
	moved to — the row a client sees just before the first run of that branch.
	"""
	by_seq = {row["seq"]: row for row in rows}
	if leaf_seq is None:  # the last row
		if not rows:
			return []
		leaf_seq = rows[-1]["seq"]
	while (marker := by_seq.get(leaf_seq)) is not None and marker["type"] == "rewind":
		if marker["target_seq"] >= leaf_seq:
			raise ValueError(f"entry {leaf_seq} points forward to {marker['target_seq']}")
		leaf_seq = marker["target_seq"]
	if leaf_seq == 0:
		return []
	if leaf_seq not in by_seq:
		raise ValueError(f"entry {leaf_seq} does not exist")

	path: list[dict] = []
	seq = leaf_seq
	while seq:
		row = by_seq.get(seq)
		if row is None:
			raise ValueError(f"entry {seq} is missing from the log")
		path.append(row)
		parent = row.get("parent_seq")
		if parent is not None and parent >= seq:
			raise ValueError(f"entry {seq} points forward to {parent}")
		seq = parent
	path.reverse()
	return path


@dataclass(frozen=True)
class PendingApproval:
	"""What a paused run is still waiting on: the approval that asked, and the calls
	nobody has decided yet."""

	seq: int | None
	calls: tuple[PendingCall, ...]


@dataclass
class _OpenToolCalls:
	"""Tool calls from the newest assistant message that have not all been answered.

	Results are matched and positioned against these; the next user or assistant
	message closes them, since nothing can answer them after that.
	"""

	assistant_index: int  # where that assistant message sits in `messages`
	calls: dict[str, ToolCall]  # by call id, in the order the assistant listed them
	answered: set[str] = field(default_factory=set)

	def position(self, call_id: str) -> int:
		"""The call's place in the order the assistant listed them."""
		return list(self.calls).index(call_id)

	def insert_index(self, call_id: str) -> int:
		"""Where this call's result belongs: after the assistant message, in call order.

		Calls can run in parallel and finish out of order, but a provider expects the
		results in the order it asked for them.
		"""
		position = self.position(call_id)
		earlier = sum(1 for answered_id in self.answered if self.position(answered_id) < position)
		return self.assistant_index + 1 + earlier


@dataclass
class _OpenApproval:
	"""A pause the run is holding: the calls an `ApprovalRequired` put to a human."""

	seq: int | None  # the approval event's seq; a `resume` must name this batch
	calls: tuple[PendingCall, ...]
	answered: set[str] = field(default_factory=set)


class Transcript:
	def __init__(self, subagent_id: str | None = None) -> None:
		self.subagent_id = subagent_id  # whose conversation this is; None = the session's own
		self.messages: list[TranscriptMessage] = []
		self.leaf_seq: int = 0  # what the next committed event follows; 0 = the root
		self.model: str | None = None  # last model change on the path; None = session config
		self.credential_id: str | None = None
		self.reasoning_effort: ReasoningEffort | None = None
		self.context_tokens: int | None = None
		self.context_message_count: int = 0
		self.run_open = False  # the last run in the log never ended
		self._open_calls: _OpenToolCalls | None = None
		self._open_approval: _OpenApproval | None = None

	@classmethod
	def replay(
		cls, log: SessionLog, *, leaf_seq: int | None = None, subagent_id: str | None = None
	) -> Transcript:
		"""Rebuild the transcript from disk — the one full read, at session load.

		Only the active branch is folded; pass `leaf_seq` to preview a rewind target,
		`subagent_id` to rebuild a sub-agent's conversation instead of the session's.
		"""
		transcript = cls(subagent_id)
		rows = log.read_since(0)
		for row in active_path(rows, leaf_seq):
			transcript.record(parse_event(row))
		transcript.run_open = _last_run_open(rows, subagent_id)
		return transcript

	@property
	def pending_approval(self) -> PendingApproval | None:
		if self._open_approval is None:
			return None
		approval = self._open_approval
		undecided = tuple(call for call in approval.calls if call.id not in approval.answered)
		return PendingApproval(seq=approval.seq, calls=undecided) if undecided else None

	def record(self, event: AnyEvent) -> None:
		"""Take one committed event into account, as it happens."""
		if isinstance(event, Rewind):  # the session swaps in a transcript rebuilt from there
			self.leaf_seq = event.target_seq
			return
		assert event.seq is not None  # recorded events are committed ones
		self.leaf_seq = event.seq
		if event.subagent_id != self.subagent_id:
			return  # another agent's row: on the chain, not in this conversation
		if isinstance(event, UserMessage):
			self._close_turn()
			self.messages.append(event)
		elif isinstance(event, AssistantMessage):
			self._close_turn()
			self.messages.append(event)
			if event.tool_calls:
				self._open_calls = _OpenToolCalls(
					assistant_index=len(self.messages) - 1,
					calls={call.id: call for call in event.tool_calls},
				)
		elif isinstance(event, ToolResult):
			self._record_result(event)
		elif isinstance(event, ApprovalRequired):
			if self._open_calls is None:
				raise ValueError("approval event has no preceding assistant tool calls")
			self._open_approval = _OpenApproval(seq=event.seq, calls=tuple(event.calls))
		elif isinstance(event, RunStarted):
			self._open_approval = None
		elif isinstance(event, RunEnded):
			# a pause outlives its run: `resume` may arrive after a restart
			if event.reason != "paused":
				self._open_approval = None
		elif isinstance(event, ModelChanged):
			self.model = event.model
			self.credential_id = event.credential_id
			self.reasoning_effort = event.reasoning_effort
			self.context_tokens = None
			self.context_message_count = 0
		elif isinstance(event, Usage):
			reported_context_tokens = 0 if event.standalone else event.input_tokens + event.output_tokens
			if reported_context_tokens > 0:
				self.context_tokens = reported_context_tokens
				self.context_message_count = len(self.messages)
		elif isinstance(event, Compaction):
			self._fold_compaction(event)
		# run_error and live-only events carry no transcript state

	def _fold_compaction(self, event: Compaction) -> None:
		"""Swap messages up to the compacted sequence for the summary — in place (a
		running loop reads this list), filtered by seq (results sit in call order)."""
		if self._open_calls is not None:
			_logger.warning("Compaction arrived with an open tool-call batch; dropping the open calls")
		self._open_calls = None
		self._open_approval = None
		kept = [m for m in self.messages if m.seq is not None and m.seq > event.compact_up_to_seq]
		self.messages[:] = [
			compaction_summary_message(event.summary, seq=event.compact_up_to_seq),
			*kept,
		]
		self.context_tokens = None
		self.context_message_count = 0

	def _close_turn(self) -> None:
		"""A newer message means nothing can answer the previous turn's calls — and a
		pause is held against those calls, so it cannot outlive them either.

		The session settles every open call before it admits a newer message (resume
		answers them, abort cancels them, `missing_results` closes a crashed turn), so
		closing an unsettled turn is an invariant violation worth shouting about: the
		provider will reject the transcript from here on.
		"""
		open_calls = self._open_calls
		if open_calls is not None:
			unanswered = [call_id for call_id in open_calls.calls if call_id not in open_calls.answered]
			if unanswered:
				_logger.warning(
					"Closing a turn with unanswered tool calls %s; their results can no longer be attached",
					", ".join(unanswered),
				)
		self._open_calls = None
		self._open_approval = None

	def _record_result(self, event: ToolResult) -> None:
		open_calls = self._open_calls
		if open_calls is None or event.tool_call_id not in open_calls.calls:
			# Providers reject a result that answers no call in the open assistant message.
			_logger.warning("Dropping unmatched tool result for call %s", event.tool_call_id)
			return
		if event.tool_call_id in open_calls.answered:
			_logger.warning(
				"Dropping duplicate tool result for call %s; the first result wins", event.tool_call_id
			)
			return
		self.messages.insert(open_calls.insert_index(event.tool_call_id), event)
		open_calls.answered.add(event.tool_call_id)
		approval = self._open_approval
		# only a gated call settles the pause; a free sibling in the same turn must not
		if approval is not None and any(call.id == event.tool_call_id for call in approval.calls):
			approval.answered.add(event.tool_call_id)

	def missing_results(self) -> tuple[ToolResult, ...]:
		"""Stand-in error results for open calls nothing will ever answer.

		A run killed mid-turn leaves tool calls with no results, which a provider
		rejects outright. Calls awaiting approval are not missing — they are the pause,
		and a `resume` will answer them.
		"""
		if self._open_calls is None:
			return ()
		pending = self.pending_approval
		undecided = {call.id for call in pending.calls} if pending is not None else set()
		return tuple(
			ToolResult(
				tool_call_id=call.id,
				name=call.name,
				content=_INTERRUPTED_TOOL_CONTENT,
				is_error=True,
				details={"repair": "interrupted"},
			)
			for call in self._open_calls.calls.values()
			if call.id not in self._open_calls.answered and call.id not in undecided
		)


def _last_run_open(rows: list[dict], subagent_id: str | None) -> bool:
	for row in reversed(rows):
		if row.get("subagent_id") == subagent_id and row["type"] in ("run_started", "run_ended"):
			return row["type"] == "run_started"
	return False
