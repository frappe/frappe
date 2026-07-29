"""Sessions: config + durable log + live pub/sub, reconstructable from disk.

The store owns run lifecycle at the boundary (create/get, subscribe, publish). The
actual loop lives in `flow_server.agent`. Publishing a durable event persists it first
(assigning a seq) and then fans it out to live subscribers; the log + replay heals any
subscriber that missed a beat.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass
from enum import StrEnum
from tempfile import mkstemp
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from flow_server import config as server_config
from flow_server.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	_Event,
	parse_event,
)
from flow_server.model.credentials import CredentialStore
from flow_server.path_policy import canonical_path, is_path_allowed, normalize_roots
from flow_server.session.log import SessionLog

# client-provided session ids land in on-disk filenames — keep them to a safe slug so a
# value like "../../etc/x" can't escape the sessions dir (arbitrary file write)
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TRANSCRIPT_REPAIR_KEY = "transcript_repair"
_INTERRUPTED_TOOL_CONTENT = "Tool call interrupted before completion."


class SessionState(StrEnum):
	"""Runtime state for admitting operations on one session."""

	IDLE = "idle"
	RUNNING = "running"
	PAUSED = "paused"


@dataclass(frozen=True, slots=True)
class PendingApproval:
	"""The unresolved part of the latest durable approval batch."""

	seq: int
	calls: tuple[PendingCall, ...]


@dataclass(slots=True)
class _ToolBatch:
	assistant_seq: int
	calls: tuple[ToolCall, ...]
	resolved_ids: set[str]


class SessionConfig(BaseModel):
	"""Configuration for an agent session.

	Attributes:
		session_id: Client-provided id (else generated); lets a client keep one identity
			across its own store and the daemon (e.g. Flow Session name).
		model: The model to use.
		system_prompt: System prompt for the agent.
		tools: Built-in tools available to the agent.
		client_tools: Schemas registered by a client.
		callback_url: Where client tools are dispatched.
		callback_token: Bearer sent to the client on callbacks (shared secret).
		user_context: Opaque context passed back on callbacks.
		credential_id: Named user-global credential; inferred from model prefix when absent.
		confirm_tools: Tools that pause for approval.
		auto_approve: Unattended runs (triggers) skip approval.
		cwd: Current working directory.
		max_turns: Maximum allowed turns.
		max_output_tokens: Simple spend cap on output tokens.
		stream: Consume the model as a token stream (vs a single response).
	"""

	model_config = ConfigDict(extra="forbid")

	session_id: str | None = None
	model: str = "mock"
	system_prompt: str = "You are a helpful agent."
	tools: list[str] = Field(default_factory=lambda: ["bash", "read_file", "write", "edit", "grep"])
	client_tools: list[dict] = Field(default_factory=list)
	callback_url: str | None = None
	callback_token: str | None = None
	user_context: dict = Field(default_factory=dict)
	credential_id: str | None = None
	confirm_tools: list[str] = Field(default_factory=list)
	auto_approve: bool = False
	cwd: str = "."
	max_turns: int = 30
	max_output_tokens: int = 200_000
	stream: bool = True

	def redacted(self) -> dict:
		data = self.model_dump()
		for secret in ("callback_token",):
			if data.get(secret):
				data[secret] = "***"
		return data


class Session:
	def __init__(
		self,
		sid: str,
		config: SessionConfig,
		log: SessionLog,
		event_sink=None,
		credentials: CredentialStore | None = None,
		allowed_roots: tuple[str, ...] = (),
	):
		self.id = sid
		self.config = config
		self.log = log
		self.event_sink = event_sink  # optional (session_id, event_dict) callback, e.g. Redis
		self.credentials = credentials or CredentialStore(server_config.CREDENTIALS_PATH)
		self.allowed_roots = allowed_roots
		for repair in interrupted_tool_repairs(log):
			log.append(repair)
		self.messages: list[TranscriptMessage] = _rebuild_messages(log)
		self._subscribers: set[asyncio.Queue] = set()
		self.operation_lock = asyncio.Lock()
		self._state = SessionState.PAUSED if pending_approval(log) is not None else SessionState.IDLE
		self.run_task: asyncio.Task[None] | None = None
		self.abort = asyncio.Event()
		self.steer_queue: asyncio.Queue[str] = asyncio.Queue()

	def steer(self, content: str) -> bool:
		"""Queue a message for the active turn, unless that turn is already aborting."""
		if self.abort.is_set():
			return False
		self.steer_queue.put_nowait(content)
		return True

	def clear_steering(self) -> None:
		"""Discard steering that has not yet become part of the durable transcript."""
		while not self.steer_queue.empty():
			self.steer_queue.get_nowait()

	def request_abort(self) -> None:
		"""Signal active work first, then discard its still-queued steering."""
		self.abort.set()
		self.clear_steering()

	def reset_abort(self) -> None:
		"""Allocate the cancellation signal for a newly admitted operation."""
		self.abort = asyncio.Event()

	# --- live pub/sub -----------------------------------------------------
	def subscribe(self) -> asyncio.Queue:
		q: asyncio.Queue = asyncio.Queue()
		self._subscribers.add(q)
		return q

	def unsubscribe(self, q: asyncio.Queue) -> None:
		self._subscribers.discard(q)

	def publish(self, event: _Event) -> None:
		"""Persist (if durable), fan out to live subscribers, and forward to any sink."""
		if event.durable:
			self.log.append(event)
		for q in list(self._subscribers):
			q.put_nowait(event)
		if self.event_sink is not None:
			try:
				self.event_sink(self.id, event.model_dump(exclude_none=True))
			except Exception:  # streaming is best-effort; the log heals gaps
				pass

	def repair_interrupted_transcript(self) -> None:
		"""Persist missing tool results and refresh the provider-facing transcript."""
		published = False
		try:
			for repair in interrupted_tool_repairs(self.log):
				self.publish(repair)
				published = True
		finally:
			if published:
				self.messages = _rebuild_messages(self.log)

	@property
	def is_running(self) -> bool:
		return self._state is SessionState.RUNNING

	@property
	def state(self) -> SessionState:
		return self._state

	def _start_operation(self, coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
		"""Register an admitted operation before it can execute.

		The caller must hold ``operation_lock`` and validate the source state first.
		Both blocking and background HTTP requests use the returned task, so there is
		one lifecycle regardless of how the caller waits.
		"""
		if not self.operation_lock.locked():
			coro.close()
			raise RuntimeError("operation_lock must be held when starting a session operation")
		if self._state is SessionState.RUNNING:
			coro.close()
			raise RuntimeError("session already has an active operation")
		# Allocate a signal per admitted operation. Besides preventing a late clear
		# from losing an abort, this avoids reusing an asyncio.Event bound to an event
		# loop from an earlier request (notably across sync ASGI test/client portals).
		self.reset_abort()
		self._state = SessionState.RUNNING
		task = asyncio.create_task(self._run_operation(coro))
		task.add_done_callback(_retrieve_task_exception)
		self.run_task = task
		return task

	async def _run_operation(self, coro: Coroutine[Any, Any, None]) -> None:
		try:
			await coro
		finally:
			async with self.operation_lock:
				if self.run_task is asyncio.current_task():
					self.run_task = None
					self._state = SessionState.IDLE
					if pending_approval(self.log) is not None:
						self._state = SessionState.PAUSED


def _retrieve_task_exception(task: asyncio.Task[None]) -> None:
	"""Mark background failures retrieved while preserving normal await semantics."""
	if not task.cancelled():
		task.exception()


class SessionStore:
	def __init__(
		self,
		data_dir: str,
		event_sink=None,
		allowed_roots: list[str] | None = None,
		credential_store: CredentialStore | None = None,
	):
		self.data_dir = data_dir
		self.sessions_dir = os.path.join(data_dir, "sessions")
		data_dir_existed = os.path.isdir(self.data_dir)
		os.makedirs(self.data_dir, mode=0o700, exist_ok=True)
		if not data_dir_existed:
			os.chmod(self.data_dir, 0o700)
		sessions_dir_existed = os.path.isdir(self.sessions_dir)
		os.makedirs(self.sessions_dir, mode=0o700, exist_ok=True)
		if not sessions_dir_existed:
			os.chmod(self.sessions_dir, 0o700)
		self.event_sink = event_sink
		configured_roots = allowed_roots if allowed_roots is not None else server_config.ALLOWED_ROOTS
		self.allowed_roots = normalize_roots(configured_roots)
		self.credentials = credential_store or CredentialStore(server_config.CREDENTIALS_PATH)
		self._cache: dict[str, Session] = {}

	def _log_path(self, sid: str) -> str:
		return os.path.join(self.sessions_dir, f"{sid}.jsonl")

	def _meta_path(self, sid: str) -> str:
		return os.path.join(self.sessions_dir, f"{sid}.meta.json")

	def create(self, config: SessionConfig) -> Session:
		self._validate_cwd(config.cwd)
		sid = config.session_id or uuid.uuid4().hex[:16]
		if not _SID_RE.match(sid):
			raise ValueError(f"invalid session_id {sid!r} (allowed: letters, digits, - _)")
		session = Session(
			sid,
			config,
			SessionLog(self._log_path(sid)),
			self.event_sink,
			self.credentials,
			self.allowed_roots,
		)
		self.save_meta(session)
		self._cache[sid] = session
		return session

	def save_meta(self, session: Session) -> None:
		"""Persist a session's config so config changes (e.g. a model override on a later
		turn) survive a restart."""
		path = self._meta_path(session.id)
		fd, tmp = mkstemp(prefix=f".{os.path.basename(path)}.", dir=self.sessions_dir)
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				json.dump(session.config.model_dump(), f)
				f.flush()
				os.fsync(f.fileno())
			os.replace(tmp, path)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)

	def _validate_cwd(self, cwd: str) -> None:
		"""Fence a session's cwd to `allowed_roots` (realpath-resolved, so symlink/`..`
		escapes can't slip past). Empty roots = unrestricted (dev default)."""
		if not self.allowed_roots:
			return
		target = canonical_path(cwd)
		if is_path_allowed(target, self.allowed_roots):
			return
		raise ValueError(f"cwd {cwd!r} is not under an allowed root")

	def get(self, sid: str) -> Session:
		if sid in self._cache:
			return self._cache[sid]
		meta_path = self._meta_path(sid)
		if not os.path.isfile(meta_path):
			raise KeyError(sid)
		with open(meta_path, encoding="utf-8") as f:
			raw_config = json.load(f)
		raw_config.pop("api_key", None)
		raw_config.pop("api_base", None)
		config = SessionConfig.model_validate(raw_config)
		self._validate_cwd(config.cwd)
		session = Session(
			sid,
			config,
			SessionLog(self._log_path(sid)),
			self.event_sink,
			self.credentials,
			self.allowed_roots,
		)
		self._cache[sid] = session
		return session

	def exists(self, sid: str) -> bool:
		return sid in self._cache or os.path.isfile(self._meta_path(sid))


def _rebuild_messages(log: SessionLog) -> list[TranscriptMessage]:
	"""Reconstruct the LLM message transcript from durable log entries."""
	rows = log.read_since(0)
	repairs: dict[int, dict[str, dict]] = {}
	for raw in rows:
		if raw.get("type") != "tool_result":
			continue
		assistant_seq = _repair_assistant_seq(raw)
		if assistant_seq is not None:
			repairs.setdefault(assistant_seq, {})[str(raw.get("tool_call_id"))] = raw

	messages: list[TranscriptMessage] = []
	pending_calls: tuple[ToolCall, ...] = ()
	pending_seq: int | None = None
	results: dict[str, dict] = {}

	def flush_results() -> None:
		nonlocal pending_calls, pending_seq, results
		if pending_seq is not None:
			results = {**repairs.get(pending_seq, {}), **results}
			for call in pending_calls:
				if call.id in results:
					messages.append(_tool_message(results[call.id]))
		pending_calls = ()
		pending_seq = None
		results = {}

	for raw in rows:
		ev = parse_event(raw)
		if ev.type == "user_message":
			flush_results()
			messages.append(ev)
		elif ev.type == "assistant_message":
			flush_results()
			messages.append(ev)
			if ev.tool_calls:
				pending_calls = tuple(ev.tool_calls)
				pending_seq = raw["seq"]
		elif ev.type == "tool_result":
			if _repair_assistant_seq(raw) is not None:
				continue
			if pending_seq is not None and any(call.id == ev.tool_call_id for call in pending_calls):
				results.setdefault(ev.tool_call_id, raw)  # first answer wins
			# a result answering no open call is dropped; providers reject an unpaired one
	flush_results()
	return messages


def _tool_message(raw: dict) -> ToolResult:
	return ToolResult.model_validate(raw)


def _repair_assistant_seq(raw: dict) -> int | None:
	details = raw.get("details")
	if not isinstance(details, dict):
		return None
	repair = details.get(_TRANSCRIPT_REPAIR_KEY)
	if not isinstance(repair, dict):
		return None
	assistant_seq = repair.get("assistant_seq")
	return assistant_seq if isinstance(assistant_seq, int) else None


def interrupted_tool_repairs(log: SessionLog) -> tuple[ToolResult, ...]:
	"""Build synthetic error results for unresolved non-approval tool calls.

	Repairs carry the originating assistant event's sequence number. Replay uses
	that marker to place a later-appended repair beside its original tool batch
	without rewriting the append-only JSONL log.
	"""
	rows = log.read_since(0)
	batches: dict[int, _ToolBatch] = {}
	approval_batches: dict[int, int] = {}
	current_batch: _ToolBatch | None = None

	for raw in rows:
		event_type = raw.get("type")
		if event_type == "assistant_message":
			event = AssistantMessage.model_validate(raw)
			if not event.tool_calls:
				current_batch = None
				continue
			assistant_seq = raw["seq"]
			current_batch = _ToolBatch(assistant_seq, tuple(event.tool_calls), set())
			batches[assistant_seq] = current_batch
		elif event_type == "tool_result":
			event = ToolResult.model_validate(raw)
			repair_seq = _repair_assistant_seq(raw)
			batch = batches.get(repair_seq) if repair_seq is not None else current_batch
			if batch is not None and any(call.id == event.tool_call_id for call in batch.calls):
				batch.resolved_ids.add(event.tool_call_id)
		elif event_type == "user_message":
			current_batch = None
		elif event_type == "approval_required":
			ApprovalRequired.model_validate(raw)
			if current_batch is None:
				raise ValueError("approval event has no preceding assistant tool batch")
			approval_batches[raw["seq"]] = current_batch.assistant_seq

	approval = pending_approval(log)
	pending_batch_seq = approval_batches.get(approval.seq) if approval is not None else None
	pending_ids = {call.id for call in approval.calls} if approval is not None else set()
	repairs: list[ToolResult] = []
	for batch in batches.values():
		for call in batch.calls:
			if call.id in batch.resolved_ids:
				continue
			if batch.assistant_seq == pending_batch_seq and call.id in pending_ids:
				continue
			repairs.append(
				ToolResult(
					tool_call_id=call.id,
					name=call.name,
					content=_INTERRUPTED_TOOL_CONTENT,
					is_error=True,
					details={
						_TRANSCRIPT_REPAIR_KEY: {
							"assistant_seq": batch.assistant_seq,
							"reason": "interrupted",
						}
					},
				)
			)

	return tuple(repairs)


def pending_approval(log: SessionLog) -> PendingApproval | None:
	"""Return unresolved calls from the latest durable approval batch.

	Tool-call ids are scoped to their approval event. Results from an older batch
	with a reused id must not resolve a newer call.
	"""
	approval_seq: int | None = None
	calls: tuple[PendingCall, ...] = ()
	resolved: set[str] = set()
	for raw in log.read_since(0):
		event_type = raw.get("type")
		if event_type == "run_started":
			approval_seq = None
			calls = ()
			resolved.clear()
		elif event_type == "approval_required":
			event = ApprovalRequired.model_validate(raw)
			approval_seq = raw["seq"]
			calls = tuple(event.calls)
			resolved.clear()
		elif event_type == "tool_result" and approval_seq is not None:
			resolved.add(str(raw.get("tool_call_id")))
		elif event_type == "run_ended" and raw.get("reason") != "paused":
			approval_seq = None
			calls = ()
			resolved.clear()

	if approval_seq is None:
		return None
	unresolved = tuple(call for call in calls if call.id not in resolved)
	return PendingApproval(seq=approval_seq, calls=unresolved) if unresolved else None
