"""One session's lifecycle: one operation at a time, the single commit point, settlement.

The session drives the pure agent loop. `run`/`resume` start one operation at a time
under a lock and spawn a task that pulls the loop's events through `_commit` — the only
place anything is persisted, folded into the transcript, and fanned out to subscribers
and the sink. When the loop raises instead of finishing its protocol, `_drive` settles
the run in one place: stand-in results close the interrupted turn (before any newer
message, so position keeps them attached), then the terminal events.

State is derived, not tracked: a session is RUNNING while its task is alive, PAUSED
while the transcript holds an undecided approval, else IDLE.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from flow import config as server_config
from flow.agent import loop
from flow.agent.loop import AfterHook, BeforeHook
from flow.events import (
	AnyEvent,
	AssistantMessage,
	ModelChanged,
	ProviderErrorKind,
	ReasoningEffort,
	Rewind,
	RunEnded,
	RunError,
	ToolResult,
	parse_event,
)
from flow.model import Model, ProviderError
from flow.model.base import ModelCancelled
from flow.model.credentials import CredentialStore
from flow.session.config import SessionConfig
from flow.session.log import SessionLog
from flow.session.transcript import PendingApproval, Transcript

_CANCELLED = json.dumps({"status": "cancelled", "message": "User cancelled this pending tool call."})


class SessionState(StrEnum):
	IDLE = "idle"
	RUNNING = "running"
	PAUSED = "paused"


class SessionConflict(Exception):
	"""The session's current state does not admit the requested operation."""


class ResumeError(ValueError):
	"""The requested continuation does not match the current approval batch."""


class RewindError(ValueError):
	"""The requested rewind target does not exist or is not a clean branch point."""


def validate_resume(
	approval: PendingApproval | None,
	approval_seq: int | None,
	answers: dict[str, str],
) -> None:
	if approval is None:
		raise ResumeError("No tool calls are awaiting approval.")
	if approval_seq is not None and approval_seq != approval.seq:
		raise ResumeError(f"Approval batch {approval_seq} is stale; current batch is {approval.seq}.")

	expected = {call.id for call in approval.calls}
	if len(expected) != len(approval.calls):
		raise ResumeError("The pending approval batch contains duplicate tool-call ids.")
	supplied = set(answers)
	if supplied == expected:
		return

	missing = sorted(expected - supplied)
	extra = sorted(supplied - expected)
	details = []
	if missing:
		details.append(f"missing answers for: {', '.join(missing)}")
	if extra:
		details.append(f"unexpected answers for: {', '.join(extra)}")
	raise ResumeError("Answers must exactly match the pending tool calls (" + "; ".join(details) + ").")


@dataclass(frozen=True)
class RunHandle:
	"""What `run`/`resume` hand back: the started operation's task, or confirmation the
	message was steered into the already-active run."""

	status: Literal["started", "steered"]
	from_seq: int  # the log cursor before the operation; replay from here to watch it
	task: asyncio.Task[None] | None = None


class Session:
	def __init__(
		self,
		sid: str,
		config: SessionConfig,
		log: SessionLog,
		*,
		event_sink=None,  # optional (session_id, event_dict) callback, e.g. Redis
		credentials: CredentialStore | None = None,
		allowed_roots: tuple[str, ...] = (),
	):
		self.id = sid
		self.config = config
		self.log = log
		self.event_sink = event_sink
		self.credentials = credentials or CredentialStore(server_config.CREDENTIALS_PATH)
		self.allowed_roots = allowed_roots
		self.transcript = Transcript.replay(log)
		self.abort_signal = asyncio.Event()
		self._operation_lock = asyncio.Lock()
		self._task: asyncio.Task[None] | None = None
		self._operation_type: Literal["run", "compact"] = "run"
		self._steering_queue: deque[str] = deque()
		self._subscribers: set[asyncio.Queue[AnyEvent]] = set()
		# a run this process never settled (daemon crash) left open calls; close them
		# now, before anything newer can be admitted
		for repair in self.transcript.missing_results():
			self._commit(repair)

	# --- state ------------------------------------------------------------

	@property
	def state(self) -> SessionState:
		if self._task is not None and not self._task.done():
			return SessionState.RUNNING
		if self.transcript.pending_approval is not None:
			return SessionState.PAUSED
		return SessionState.IDLE

	@property
	def is_running(self) -> bool:
		return self.state is SessionState.RUNNING

	@property
	def model(self) -> str:
		"""The effective model: the last model change on the active branch, else config."""
		return self.transcript.model or self.config.model

	@property
	def credential_id(self) -> str | None:
		# the selection travels as a pair: once a model change exists, its credential wins
		if self.transcript.model is not None:
			return self.transcript.credential_id
		return self.config.credential_id

	@property
	def reasoning_effort(self) -> ReasoningEffort | None:
		# effort travels with the selection, same as the credential
		if self.transcript.model is not None:
			return self.transcript.reasoning_effort
		return self.config.reasoning_effort

	# --- verbs ------------------------------------------------------------

	async def run(
		self,
		message: str,
		*,
		model: Model | None = None,
		before_tool_call: BeforeHook | None = None,
		after_tool_call: AfterHook | None = None,
	) -> RunHandle:
		"""Start a turn — or steer the message into the turn already running."""
		async with self._operation_lock:
			if self.state is SessionState.PAUSED:
				raise SessionConflict("run is paused for approval; resolve it with resume")
			if self.state is SessionState.RUNNING:
				if self.abort_signal.is_set():
					raise SessionConflict("run is aborting")
				if self._operation_type != "run":
					# compaction never drains steering; "steered" would delay or lose the message
					raise SessionConflict("compaction is in progress; run again when it finishes")
				self._steering_queue.append(message)
				return RunHandle(status="steered", from_seq=self.log.latest_seq)
			inputs = self._loop_inputs(model, before_tool_call, after_tool_call)
			return self._start_operation(loop.run(message, inputs))

	async def resume(
		self,
		answers: dict[str, str],
		*,
		approval_seq: int | None = None,
		model: Model | None = None,
		before_tool_call: BeforeHook | None = None,
		after_tool_call: AfterHook | None = None,
	) -> RunHandle:
		"""Continue a paused run with a decision per pending call."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("run is not paused")
			approval = self.transcript.pending_approval
			validate_resume(approval, approval_seq, answers)
			assert approval is not None  # narrowed by validate_resume
			inputs = self._loop_inputs(model, before_tool_call, after_tool_call)
			return self._start_operation(loop.resume(approval, answers, inputs))

	def abort(self) -> bool:
		"""Signal the active run to stop; steering that never became durable dies with it."""
		if not self.is_running:
			return False
		self.abort_signal.set()
		self._steering_queue.clear()
		return True

	async def rewind(self, target_seq: int) -> None:
		"""Move the conversation back to an earlier entry; the next run branches from it.

		Target 0 rewinds to before everything. Any other target must leave no
		unanswered tool calls and no pending approval."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("a run is already active")
			try:
				candidate = Transcript.replay(self.log, leaf_seq=target_seq)
			except ValueError as error:
				raise RewindError(str(error)) from None
			if candidate.missing_results() or candidate.pending_approval is not None:
				raise RewindError(f"entry {target_seq} leaves tool calls unanswered")
			self._commit(Rewind(target_seq=target_seq))
			self.transcript = candidate

	async def set_model(
		self,
		model: str,
		credential_id: str | None = None,
		reasoning_effort: ReasoningEffort | None = None,
	) -> None:
		"""Select the model (with credential and reasoning effort) for runs from here on —
		a durable entry, so it survives restarts and rewinds away with its branch."""
		if not model:
			raise ValueError("model must be a non-empty name")
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("a run is already active")
			if (model, credential_id, reasoning_effort) == (
				self.model,
				self.credential_id,
				self.reasoning_effort,
			):
				return
			self._commit(
				ModelChanged(model=model, credential_id=credential_id, reasoning_effort=reasoning_effort)
			)

	async def compact(
		self,
		instructions: str | None = None,
		*,
		model: Model | None = None,
	) -> RunHandle:
		"""Summarize the whole conversation into a durable compaction entry; the
		replaced rows stay in the log."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("a run is already active")
			if self.state is SessionState.PAUSED:
				raise SessionConflict("run is paused for approval; resolve it before compacting")
			if not self.transcript.messages:
				raise SessionConflict("nothing to compact")
			inputs = self._loop_inputs(model, None, None)
			return self._start_operation(
				loop.compact(instructions, inputs),
				operation_type="compact",
			)

	async def cancel_pending(self) -> bool:
		"""Abandon a paused run's approval batch: answer every undecided call with a
		cancellation so the transcript closes and the session returns to idle."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("a run is already active")
			approval = self.transcript.pending_approval
			if approval is None:
				return False
			for call in approval.calls:
				self._commit(
					ToolResult(tool_call_id=call.id, name=call.name, content=_CANCELLED, is_error=True)
				)
			return True

	# --- live subscription ------------------------------------------------

	def subscribe(self) -> asyncio.Queue[AnyEvent]:
		queue: asyncio.Queue[AnyEvent] = asyncio.Queue()
		self._subscribers.add(queue)
		return queue

	def unsubscribe(self, queue: asyncio.Queue[AnyEvent]) -> None:
		self._subscribers.discard(queue)

	async def events(self, since: int = 0) -> AsyncGenerator[AnyEvent]:
		"""Replay the log from a cursor, then stay attached to the live stream.

		The one subscription surface: SSE and embedded callers both read this. The
		subscription opens before the replay so nothing can fall between them; a
		durable event seen by both sides is deduplicated by seq.
		"""
		queue = self.subscribe()
		try:
			cursor = since
			for row in self.log.read_since(since):
				cursor = row["seq"]
				yield parse_event(row)
			while True:
				event = await queue.get()
				if event.durable and event.seq is not None and event.seq <= cursor:
					continue
				yield event
		finally:
			self.unsubscribe(queue)

	# --- the one writer ---------------------------------------------------

	def _commit(self, event: AnyEvent) -> None:
		"""Persist (if durable), fold into the transcript, fan out, forward to the sink."""
		if event.durable:
			event.parent_seq = self.transcript.leaf_seq  # after a rewind, not the last row
			self.log.append(event)
			self.transcript.record(event)
		for queue in list(self._subscribers):
			queue.put_nowait(event)
		if self.event_sink is not None:
			try:
				self.event_sink(self.id, event.model_dump(exclude_none=True))
			except Exception:  # streaming is best-effort; the log heals gaps
				pass

	# --- driving one admitted operation -----------------------------------

	def _start_operation(
		self,
		events: AsyncIterator[AnyEvent],
		*,
		operation_type: Literal["run", "compact"] = "run",
	) -> RunHandle:
		from_seq = self.log.latest_seq
		self._operation_type = operation_type
		task = asyncio.create_task(self._drive(events, operation_type=operation_type))
		task.add_done_callback(_mark_retrieved)
		self._task = task
		return RunHandle(status="started", from_seq=from_seq, task=task)

	def _loop_inputs(
		self, model: Model | None, before_tool_call: BeforeHook | None, after_tool_call: AfterHook | None
	) -> loop.LoopInputs:
		"""Prepare a fresh operation's inputs — including its own abort signal, so a
		late abort of the previous run cannot leak into this one."""
		self.abort_signal = asyncio.Event()
		return loop.LoopInputs(
			config=self.config,
			messages=self.transcript.messages,
			credentials=self.credentials,
			abort=self.abort_signal,
			model_name=self.model,
			credential_id=self.credential_id,
			reasoning_effort=self.reasoning_effort,
			allowed_roots=self.allowed_roots,
			session_id=self.id,
			model=model,
			context_tokens=self.transcript.context_tokens,
			context_message_count=self.transcript.context_message_count,
			next_steering=self._next_steering,
			before_tool_call=before_tool_call,
			after_tool_call=after_tool_call,
		)

	def _next_steering(self) -> str | None:
		return self._steering_queue.popleft() if self._steering_queue else None

	async def _drive(
		self, events: AsyncIterator[AnyEvent], *, operation_type: Literal["run", "compact"]
	) -> None:
		"""Commit the loop's events; when it raises instead, settle the run here."""
		aborted_terminal = False
		try:
			async for event in events:
				if isinstance(event, AssistantMessage) and event.stop_reason == "aborted":
					aborted_terminal = True
				self._commit(event)
		except (ModelCancelled, asyncio.CancelledError) as cancelled:
			self._settle(
				reason="aborted",
				needs_aborted_message=operation_type == "run" and not aborted_terminal,
			)
			if isinstance(cancelled, asyncio.CancelledError):
				raise
		except Exception as error:
			self._settle(reason="error", error=error)

	def _settle(
		self,
		*,
		reason: Literal["aborted", "error"],
		needs_aborted_message: bool = False,
		error: Exception | None = None,
	) -> None:
		"""Close an interrupted run: repairs first (position attaches them to their
		turn), then the terminal protocol the loop never got to yield."""
		for repair in self.transcript.missing_results():
			self._commit(repair)
		if needs_aborted_message:
			self._commit(
				AssistantMessage(
					provider=self.model.partition("/")[0],
					model=self.model,
					stop_reason="aborted",
				)
			)
		if error is not None:
			provider_error = error if isinstance(error, ProviderError) else None
			kind: ProviderErrorKind | None = provider_error.kind if provider_error else None
			self._commit(
				RunError(
					message=f"{type(error).__name__}: {error}",
					kind=kind,
					retryable=provider_error.retryable if provider_error else None,
					status_code=provider_error.status_code if provider_error else None,
					provider=provider_error.provider if provider_error else None,
					detail=provider_error.detail if provider_error else None,
				)
			)
		self._commit(RunEnded(reason=reason))


def _mark_retrieved(task: asyncio.Task[None]) -> None:
	"""Mark background failures retrieved while preserving normal await semantics."""
	if not task.cancelled():
		task.exception()
