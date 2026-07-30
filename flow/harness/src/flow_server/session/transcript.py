"""Turns the event log into the state a session needs while it runs.

State is maintained in real time: the session calls `record` on each event as it is
committed, so nothing here ever re-reads the log mid-run. Reading the whole log happens
exactly once, at load — `replay` rebuilds a transcript by pushing every logged event
through that same `record`, so a restarted session and a live one always agree.

It keeps three things current:
  - `messages`: the conversation in the shape a provider accepts, with each tool
    result placed right after the call it answers.
  - the open tool calls: the newest assistant message whose tool calls have not all
    come back yet. Incoming results are matched against them.
  - `pending_approval`: the calls a paused run is waiting for a human to decide.

A result is matched against whichever tool calls are open when it arrives. So the
stand-in results that close an interrupted turn (`missing_results`) have to reach the
log before any newer message does; the session writes them when it admits the next run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from flow_server.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	RunStarted,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	UserMessage,
	parse_event,
)
from flow_server.session.log import SessionLog

_INTERRUPTED_TOOL_CONTENT = "Tool call interrupted before completion."
_logger = logging.getLogger(__name__)


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
	def __init__(self) -> None:
		self.messages: list[TranscriptMessage] = []
		self._open_calls: _OpenToolCalls | None = None
		self._open_approval: _OpenApproval | None = None

	@classmethod
	def replay(cls, log: SessionLog) -> Transcript:
		"""Rebuild the transcript from disk — the one full read, at session load."""
		transcript = cls()
		for row in log.read_since(0):
			transcript.record(parse_event(row))
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
		# usage, run_error, and live-only events carry no transcript state

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
