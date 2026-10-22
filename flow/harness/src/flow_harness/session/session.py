"""One session's lifecycle: one operation at a time, the single commit point, settlement.

The session drives the pure agent loop. `run`/`resume` start one operation at a time
under a lock and spawn a task that pulls the loop's events through `_commit` — the only
place anything is persisted, folded into the transcript, and fanned out to subscribers
and the sink. When the loop raises instead of finishing its protocol, `_drive` settles
the run in one place: stand-in results close the interrupted turn (before any newer
message, so position keeps them attached), then the terminal events.

State is derived, not tracked: a session is RUNNING while its task is alive, PAUSED
while the transcript holds an undecided approval, else IDLE.

A sub-agent the `subagent` tool starts runs inside the session's own task, driven by
`SubagentRunner`: its events go through the same `_commit`, tagged with its id, and an
approval it pauses for is answered through `resume` while the session stays RUNNING.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from flow_harness import config as server_config
from flow_harness.agent import loop
from flow_harness.agent.client_tools import notify_run_ended
from flow_harness.agent.loop import AfterHook, BeforeHook
from flow_harness.events import (
	AnyEvent,
	AssistantContent,
	AssistantMessage,
	AttachmentContent,
	ModelChanged,
	PreviewReplayStarted,
	ProviderErrorKind,
	ReasoningEffort,
	Retry,
	Rewind,
	RunEnded,
	RunError,
	RunStarted,
	TextContent,
	TextDelta,
	ThinkingContent,
	ThinkingDelta,
	TitleChanged,
	ToolCallDisplayReady,
	ToolCallStarted,
	ToolResult,
	UserMessage,
	parse_event,
)
from flow_harness.model import Model, ProviderError, get_model
from flow_harness.model.auth import resolve_model_auth
from flow_harness.model.cancellation import ModelCancelled
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.reasoning import reasoning_params
from flow_harness.session import titling
from flow_harness.session.attachments import (
	MAX_ATTACHMENTS_PER_MESSAGE,
	MAX_TEXT_BYTES,
	AttachmentError,
	AttachmentStore,
)
from flow_harness.session.config import SessionConfig
from flow_harness.session.log import SessionLog
from flow_harness.session.prompt import doc_roots
from flow_harness.session.skills import (
	Skill,
	SkillCatalog,
	format_skill_invocation,
	parse_skill_command,
	sorted_skills,
)
from flow_harness.session.subagents import CANCELLED, SubagentRunner
from flow_harness.session.transcript import PendingApproval, Transcript
from flow_harness.tools import Tool

if TYPE_CHECKING:
	from pathlib import Path

	from flow_harness.extensions import ExtensionRuntime

_SUBSCRIBER_QUEUE_SIZE = 256
INTERRUPTED = "The flow server stopped before this run ended."


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
	message was steered into the already-active run or the answers reached a paused
	sub-agent."""

	status: Literal["started", "steered", "resumed"]
	from_seq: int  # the log cursor before the operation; replay from here to watch it
	task: asyncio.Task[None] | None = None


@dataclass(frozen=True)
class _QueuedSteering:
	message: UserMessage
	owned_attachment_claims: tuple[str, ...] = ()


@dataclass
class _PartialAssistant:
	"""Displayable blocks seen only as live deltas in the current model attempt.

	Providers normally turn these into the terminal ``AssistantMessage`` themselves.
	The session also races the provider iterator against abort so a misbehaving adapter
	cannot hold a run open; if that outer race wins, this is the durable fallback.
	"""

	content: list[AssistantContent] = field(default_factory=list)
	_tail_kind: Literal["text", "thinking"] | None = None

	def observe(self, event: AnyEvent) -> None:
		if isinstance(event, TextDelta):
			if self._tail_kind == "text" and isinstance(self.content[-1], TextContent):
				self.content[-1].text += event.text
			else:
				self.content.append(TextContent(text=event.text))
			self._tail_kind = "text"
		elif isinstance(event, ThinkingDelta):
			if self._tail_kind == "thinking" and isinstance(self.content[-1], ThinkingContent):
				self.content[-1].thinking += event.thinking
			else:
				self.content.append(ThinkingContent(thinking=event.thinking))
			self._tail_kind = "thinking"
		elif isinstance(event, (ToolCallStarted, ToolCallDisplayReady)):
			# These are presentation-only; the provider's terminal message remains the
			# single canonical tool call. Both still separate adjacent streamed blocks.
			self._tail_kind = None
		elif isinstance(event, Retry) and event.status == "started":
			# The fresh attempt restreams from scratch.
			self.content = []
			self._tail_kind = None
		elif isinstance(event, AssistantMessage):
			# The provider supplied the canonical terminal, so no fallback is needed.
			self.content = []
			self._tail_kind = None


class Session:
	def __init__(
		self,
		sid: str,
		config: SessionConfig,
		log: SessionLog,
		*,
		event_sink: Callable[[str, dict], None] | None = None,
		credential_store: CredentialStore | None = None,
		allowed_roots: tuple[str, ...] = (),
		ignore_hidden_files: bool = False,
		attachment_store: AttachmentStore | None = None,
		skill_catalog: SkillCatalog | None = None,
		server_tools: dict[str, Tool] | None = None,
		extension_runtime: ExtensionRuntime | None = None,
		persist_meta: Callable[[Session], None] | None = None,
		resolve_skill: Callable[[str], Skill | None] | None = None,
		persist_skill_catalog: Callable[[Session], None] | None = None,
		on_settled: Callable[[Session], None] | None = None,
		on_first_message: Callable[[Session], None] | None = None,
		compose_tools: Callable[[SessionConfig], dict[str, Tool]],
		run_end_marker: Path,
	):
		self.id = sid
		self.config = config
		self.log = log
		self.run_end_marker = run_end_marker  # present while a run end is unconfirmed
		self._seq_before_last_run = 0  # the log's latest seq when the last run started
		self.event_sink = event_sink
		self.credential_store = credential_store or CredentialStore(server_config.CREDENTIALS_PATH)
		self.allowed_roots = allowed_roots
		self.ignore_hidden_files = ignore_hidden_files
		self.attachment_store = attachment_store
		self.skill_catalog = skill_catalog or SkillCatalog()
		self.server_tools = server_tools
		self.extension_runtime = extension_runtime
		self._persist_meta = persist_meta
		self._resolve_skill = resolve_skill
		self._persist_skill_catalog = persist_skill_catalog
		self._on_settled = on_settled
		self._on_first_message = on_first_message
		self._subagent_runner = SubagentRunner(
			self._commit, _run_error, compose_tools, log, config.max_concurrent_subagents
		)
		self.transcript = Transcript.replay(log)
		self.abort_signal = asyncio.Event()
		self._budget = loop.TokenBudget(config.token_budget)
		self._operation_lock = asyncio.Lock()
		self._task: asyncio.Task[None] | None = None
		self._title_task: asyncio.Task[None] | None = None
		self._operation_type: Literal["run", "compact"] = "run"
		self._steering_queue: deque[_QueuedSteering] = deque()
		self._subscribers: set[asyncio.Queue[AnyEvent | None]] = set()
		self._preview_replay: list[AnyEvent] = []
		self._stream_id = uuid.uuid4().hex
		self._revision = 0
		# a run this process never settled (daemon crash) left open calls; close them
		# now, before anything newer can be admitted
		for repair in self.transcript.missing_results():
			self._commit(repair)
		if self.transcript.run_open:  # the run itself never ended either
			self._commit(RunError(message=INTERRUPTED))
			self._commit(RunEnded(reason="error"))

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
	def in_use(self) -> bool:
		"""Something in this process still needs the object itself: a run, a live
		stream, or a title being written. Anything else can be rebuilt from the log."""
		return (
			self.is_running
			or bool(self._subscribers)
			or (self._title_task is not None and not self._title_task.done())
		)

	def _settled(self, _task: asyncio.Task[None] | None = None) -> None:
		"""An `in_use` reason cleared; the store may now re-cost or drop this object."""
		if self._on_settled is not None:
			self._on_settled(self)

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
		attachment_ids: list[str] | None = None,
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
				user_message, owned_attachment_claims = self._user_message(message, attachment_ids or [])
				self._steering_queue.append(_QueuedSteering(user_message, owned_attachment_claims))
				return RunHandle(status="steered", from_seq=self.log.latest_seq)
			user_message, _ = self._user_message(message, attachment_ids or [])
			should_title = self._should_title()
			# a rewind to the start empties the transcript, not the log
			if (
				self._on_first_message is not None
				and not any(isinstance(m, UserMessage) for m in self.transcript.messages)
				and not any(row["type"] == "user_message" for row in self.log.read_since(0))
			):
				self._on_first_message(self)
			self._budget = loop.TokenBudget(self.config.token_budget)
			inputs = self._loop_inputs(model, before_tool_call, after_tool_call)
			handle = self._start_operation(loop.run(user_message, inputs))
			if should_title:
				self._start_titling(user_message.text)
			return handle

	async def resume(
		self,
		answers: dict[str, str],
		*,
		approval_seq: int | None = None,
		model: Model | None = None,
		before_tool_call: BeforeHook | None = None,
		after_tool_call: AfterHook | None = None,
	) -> RunHandle:
		"""Continue a paused run with a decision per pending call. A batch a sub-agent
		waits on goes to it, while the session keeps running."""
		async with self._operation_lock:
			batch = self._subagent_runner.pending(approval_seq)
			if batch is not None:
				validate_resume(batch, approval_seq, answers)
				self._subagent_runner.answer(approval_seq, answers)
				return RunHandle(status="resumed", from_seq=self.log.latest_seq)
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
		self._discard_steering()
		return True

	async def rewind(self, target_seq: int) -> None:
		"""Move the conversation back to an earlier entry; the next run branches from it.

		Target 0 rewinds to before everything. Any other target must leave no
		unanswered tool calls and no pending approval."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				raise SessionConflict("a run is already active")
			if self.state is SessionState.PAUSED:
				raise SessionConflict("run is paused for approval; resolve it before rewinding")
			try:
				candidate = Transcript.replay(self.log, leaf_seq=target_seq)
			except ValueError as error:
				raise RewindError(str(error)) from None
			if candidate.missing_results() or candidate.pending_approval is not None:
				raise RewindError(f"entry {target_seq} leaves tool calls unanswered")
			# the branch point the target resolved to: a marker never anchors a chain
			self._commit(Rewind(target_seq=candidate.leaf_seq))
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
		cancellation so the transcript closes and the session returns to idle, dropping any
		steering that waited on it. While the session runs, this abandons the batches its
		sub-agents wait on instead."""
		async with self._operation_lock:
			if self.state is SessionState.RUNNING:
				if self._subagent_runner.cancel_pending():
					return True
				raise SessionConflict("a run is already active")
			approval = self.transcript.pending_approval
			if approval is None:
				return False
			for call in approval.calls:
				self._commit(
					ToolResult(tool_call_id=call.id, name=call.name, content=CANCELLED, is_error=True)
				)
			self._discard_steering()
			return True

	def report_run_end(self) -> None:
		"""Tell the client the latest run ended, retrying until it confirms."""
		if self.config.notify_run_ended:
			task = asyncio.create_task(self._deliver_run_end(self.log.latest_seq))
			task.add_done_callback(_mark_retrieved)

	async def _deliver_run_end(self, terminal_seq: int) -> None:
		confirmed = await notify_run_ended(
			self.config, self.id, terminal_seq, still_needed=self.run_end_marker.exists
		)
		if confirmed and self._seq_before_last_run < terminal_seq:  # a run started since keeps the marker
			self.run_end_marker.unlink(missing_ok=True)

	# --- live subscription ------------------------------------------------

	def subscribe(self) -> asyncio.Queue[AnyEvent | None]:
		queue: asyncio.Queue[AnyEvent | None] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
		self._subscribers.add(queue)
		return queue

	def unsubscribe(self, queue: asyncio.Queue[AnyEvent | None]) -> None:
		self._subscribers.discard(queue)
		if not self._subscribers:
			self._settled()

	async def events(self, since: int = 0) -> AsyncGenerator[AnyEvent]:
		"""Replay stored events, then follow the live stream.

		Subscribe before replay to avoid gaps. Skip durable duplicates by sequence
		number, and capture the active preview at the same point.
		"""
		queue = self.subscribe()
		preview_replay = tuple(self._preview_replay)
		try:
			cursor = since
			for row in self.log.read_since(since):
				cursor = row["seq"]
				yield parse_event(row)
			if preview_replay:
				yield PreviewReplayStarted()
				for event in preview_replay:
					yield event
			while True:
				event = await queue.get()
				if event is None:
					return
				if event.durable and event.seq is not None and event.seq <= cursor:
					continue
				yield event
		finally:
			self.unsubscribe(queue)

	def event_snapshot(self, since: int = 0) -> dict:
		"""Return durable events and the current preview."""
		return {
			"entries": self.log.read_since(since),
			"preview": [event.model_dump(exclude_none=True) for event in self._preview_replay],
			"latest_seq": self.log.latest_seq,
			"state": self.state,
			"running": self.is_running,
			"stream_id": self._stream_id,
			"revision": self._revision,
		}

	# --- the one writer ---------------------------------------------------

	def _commit(self, event: AnyEvent) -> None:
		"""Persist (if durable), fold into the transcript, fan out, forward to the sink."""
		if event.durable:
			if isinstance(event, RunStarted) and event.subagent_id is None and self.config.notify_run_ended:
				self.run_end_marker.touch()  # before the row, so a crash from here on is still reported
				self._seq_before_last_run = self.log.latest_seq
			event.parent_seq = self.transcript.leaf_seq  # after a rewind, not the last row
			self.log.append(event)
			if event.subagent_id is None and isinstance(event, (RunStarted, AssistantMessage, RunEnded)):
				self._preview_replay.clear()
			self.transcript.record(event)
		elif event.subagent_id is None:  # a sub-agent's preview is not replayed
			self._retain_preview(event)
		for queue in list(self._subscribers):
			try:
				queue.put_nowait(event)
			except asyncio.QueueFull:
				self.unsubscribe(queue)
				while not queue.empty():
					queue.get_nowait()
				queue.put_nowait(None)
		self._revision += 1
		if self.event_sink is not None:
			try:
				self.event_sink(
					self.id,
					{
						**event.model_dump(exclude_none=True),
						"stream_id": self._stream_id,
						"revision": self._revision,
					},
				)
			except Exception:  # streaming is best-effort; the log heals gaps
				pass

	def _retain_preview(self, event: AnyEvent) -> None:
		"""Keep the live preview a late subscriber needs to rebuild the run so far."""
		if isinstance(event, Retry) and event.status == "started":
			self._preview_replay[:] = [event]
		elif isinstance(event, TextDelta):
			previous = self._preview_replay[-1] if self._preview_replay else None
			if isinstance(previous, TextDelta):
				self._preview_replay[-1] = TextDelta(text=previous.text + event.text)
			else:
				self._preview_replay.append(event)
		elif isinstance(event, ThinkingDelta):
			previous = self._preview_replay[-1] if self._preview_replay else None
			if isinstance(previous, ThinkingDelta):
				self._preview_replay[-1] = ThinkingDelta(thinking=previous.thinking + event.thinking)
			else:
				self._preview_replay.append(event)
		elif isinstance(event, (ToolCallStarted, ToolCallDisplayReady, Retry)):
			self._preview_replay.append(event)

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
		task.add_done_callback(self._settled)
		self._task = task
		return RunHandle(status="started", from_seq=from_seq, task=task)

	def _loop_inputs(
		self, model: Model | None, before_tool_call: BeforeHook | None, after_tool_call: AfterHook | None
	) -> loop.LoopInputs:
		"""Prepare a fresh operation's inputs — including its own abort signal, so a
		late abort of the previous run cannot leak into this one."""
		self.abort_signal = asyncio.Event()
		skill_dirs = (skill.base_dir for skill in self.skill_catalog.skills)
		return loop.LoopInputs(
			config=self.config,
			messages=self.transcript.messages,
			credential_store=self.credential_store,
			abort=self.abort_signal,
			model_name=self.model,
			credential_id=self.credential_id,
			reasoning_effort=self.reasoning_effort,
			allowed_roots=self.allowed_roots,
			ignore_hidden_files=self.ignore_hidden_files,
			read_only_roots=tuple(dict.fromkeys((*skill_dirs, *doc_roots()))),
			session_id=self.id,
			model=model,
			context_tokens=self.transcript.context_tokens,
			context_message_count=self.transcript.context_message_count,
			next_steering=self._next_steering,
			before_tool_call=before_tool_call,
			after_tool_call=after_tool_call,
			resolve_attachment=self.attachment_store.read if self.attachment_store is not None else None,
			store_image=self._store_tool_image if self.attachment_store is not None else None,
			run_subagent=self._subagent_runner.run,
			server_tools=self.server_tools,
			extension_runtime=self.extension_runtime,
			budget=self._budget,
		)

	async def _store_tool_image(self, name: str, data: bytes) -> AttachmentContent:
		"""Store a tool's image and claim it at once: the result referencing it is
		committed as soon as the call returns."""
		assert self.attachment_store is not None
		stored = await asyncio.to_thread(self.attachment_store.add_bytes, name, data)
		self.attachment_store.claim([stored.id])
		return stored

	def _next_steering(self) -> UserMessage | None:
		return self._steering_queue.popleft().message if self._steering_queue else None

	def _user_message(self, message: str, attachment_ids: list[str]) -> tuple[UserMessage, tuple[str, ...]]:
		if len(attachment_ids) > MAX_ATTACHMENTS_PER_MESSAGE:
			raise AttachmentError(f"a message can include at most {MAX_ATTACHMENTS_PER_MESSAGE} attachments")
		if len(set(attachment_ids)) != len(attachment_ids):
			raise AttachmentError("a message cannot include the same attachment twice")
		invocation = parse_skill_command(message, self.skill_catalog.skills, resolve=self._resolve_skill)
		if invocation is not None:
			for item in invocation.skills:
				self._adopt_skill(item.skill)
		if not attachment_ids:
			if invocation is not None:
				return UserMessage(content=format_skill_invocation(invocation)), ()
			if not message.strip():
				raise AttachmentError("message must not be empty")
			return UserMessage(content=message), ()
		if self.attachment_store is None:
			raise AttachmentError("this session does not have attachment storage")
		attachments = [self.attachment_store.get(attachment_id) for attachment_id in attachment_ids]
		if sum(item.size for item in attachments if item.kind == "text") > MAX_TEXT_BYTES:
			raise AttachmentError(f"text attachments exceed the {MAX_TEXT_BYTES // 1024} KB message limit")
		content = (
			[TextContent(text=format_skill_invocation(invocation))]
			if invocation is not None
			else ([TextContent(text=message)] if message else [])
		)
		content.extend(attachments)
		owned_attachment_claims = self.attachment_store.claim(attachment_ids)
		return UserMessage(content=content), owned_attachment_claims

	def _adopt_skill(self, skill: Skill) -> None:
		"""Add an invoked skill to the session's catalog, so its directory stays readable."""
		if any(item.name == skill.name for item in self.skill_catalog.skills):
			return
		self.skill_catalog = self.skill_catalog.model_copy(
			update={"skills": sorted_skills((*self.skill_catalog.skills, skill))}
		)
		if self._persist_skill_catalog is not None:
			self._persist_skill_catalog(self)

	def _discard_steering(self) -> None:
		claims: list[str] = []
		for queued in self._steering_queue:
			claims.extend(queued.owned_attachment_claims)
		self._steering_queue.clear()
		if claims and self.attachment_store is not None:
			try:
				self.attachment_store.discard_claims(tuple(claims))
			except OSError:
				pass  # attachment cleanup must never prevent the run protocol from settling

	async def _drive(
		self, events: AsyncIterator[AnyEvent], *, operation_type: Literal["run", "compact"]
	) -> None:
		"""Commit the loop's events; when it raises instead, settle the run here."""
		aborted_terminal = False
		partial = _PartialAssistant()
		try:
			async for event in events:
				partial.observe(event)
				if isinstance(event, AssistantMessage) and event.stop_reason == "aborted":
					aborted_terminal = True
				if isinstance(event, RunEnded) and event.reason != "paused":
					self._discard_steering()
				self._commit(event)
		except (ModelCancelled, asyncio.CancelledError) as cancelled:
			self._settle(
				reason="aborted",
				needs_aborted_message=operation_type == "run" and not aborted_terminal,
				partial_content=partial.content,
			)
			if isinstance(cancelled, asyncio.CancelledError):
				raise
		except Exception as error:
			self._settle(reason="error", error=error)
		finally:
			self.report_run_end()

	def _settle(
		self,
		*,
		reason: Literal["aborted", "error"],
		needs_aborted_message: bool = False,
		partial_content: list[AssistantContent] | None = None,
		error: Exception | None = None,
	) -> None:
		"""Close an interrupted run: repairs first (position attaches them to their
		turn), then the terminal protocol the loop never got to yield."""
		self._discard_steering()
		for repair in self.transcript.missing_results():
			self._commit(repair)
		if needs_aborted_message:
			self._commit(
				AssistantMessage(
					content=partial_content or [],
					provider=self.model.partition("/")[0],
					model=self.model,
					stop_reason="aborted",
				)
			)
		if error is not None:
			self._commit(_run_error(error))
		self._commit(RunEnded(reason=reason))

	# --- background titling -----------------------------------------------

	def _should_title(self) -> bool:
		"""Title once, on the first message of an untitled session. Mock sessions keep
		the first-message fallback — a mock 'title' would be scripted noise."""
		return (
			self.config.title is None
			and self.model.partition("/")[0] != "mock"
			and not any(isinstance(m, UserMessage) for m in self.transcript.messages)
		)

	def _start_titling(self, first_message: str) -> None:
		task = asyncio.create_task(self._title_session(first_message))
		task.add_done_callback(_mark_retrieved)
		task.add_done_callback(self._settled)
		self._title_task = task

	def cancel_titling(self) -> None:
		if self._title_task is not None and not self._title_task.done():
			self._title_task.cancel()

	async def _title_session(self, first_message: str) -> None:
		"""Runs alongside the first turn on its own model instance, so it never blocks
		or steals the run's stream. Best-effort: any failure leaves the fallback."""
		try:
			auth = await resolve_model_auth(
				self.model,
				self.credential_store,
				provider_id=self.credential_id,
				api_key=self.config.api_key,
				api_base=self.config.api_base,
			)
			model = get_model(
				self.model,
				api_key=auth.api_key,
				api_base=auth.base_url,
				headers=auth.headers,
				params={**self.config.model_params, **(reasoning_params(self.model, "off") or {})},
				refresh_auth=auth.refresh,
			)
			title = await titling.generate_title(model, first_message)
			if title is None or self.config.title is not None:
				return
			self.config.title = title
			if self._persist_meta is not None:
				try:
					self._persist_meta(self)
				except Exception:
					self.config.title = None
					return
			self._commit(TitleChanged(title=title))
		except Exception:
			pass  # titling must never disturb the run


def _run_error(error: Exception) -> RunError:
	provider_error = error if isinstance(error, ProviderError) else None
	kind: ProviderErrorKind | None = provider_error.kind if provider_error else None
	return RunError(
		message=f"{type(error).__name__}: {error}",
		kind=kind,
		retryable=provider_error.retryable if provider_error else None,
		status_code=provider_error.status_code if provider_error else None,
		provider=provider_error.provider if provider_error else None,
		detail=provider_error.detail if provider_error else None,
	)


def _mark_retrieved(task: asyncio.Task[None]) -> None:
	"""Mark background failures retrieved while preserving normal await semantics."""
	if not task.cancelled():
		task.exception()
