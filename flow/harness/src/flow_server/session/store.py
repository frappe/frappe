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
from tempfile import mkstemp

from pydantic import BaseModel, ConfigDict, Field

from flow_server import config as server_config
from flow_server.events import _Event, parse_event
from flow_server.model.credentials import CredentialStore
from flow_server.session.log import SessionLog

# client-provided session ids land in on-disk filenames — keep them to a safe slug so a
# value like "../../etc/x" can't escape the sessions dir (arbitrary file write)
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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
	):
		self.id = sid
		self.config = config
		self.log = log
		self.event_sink = event_sink  # optional (session_id, event_dict) callback, e.g. Redis
		self.credentials = credentials or CredentialStore(server_config.CREDENTIALS_PATH)
		self.messages: list[dict] = _rebuild_messages(log)
		self._subscribers: set[asyncio.Queue] = set()
		self.run_task: asyncio.Task | None = None
		self.abort = asyncio.Event()
		self.steer_queue: asyncio.Queue[str] = asyncio.Queue()

	def steer(self, content: str) -> None:
		"""Queue a message to inject into the running turn at the next boundary."""
		self.steer_queue.put_nowait(content)

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
				self.event_sink(self.id, event.model_dump())
			except Exception:  # streaming is best-effort; the log heals gaps
				pass

	@property
	def is_running(self) -> bool:
		return self.run_task is not None and not self.run_task.done()


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
		self.allowed_roots = allowed_roots if allowed_roots is not None else server_config.ALLOWED_ROOTS
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
		target = os.path.realpath(cwd)
		for root in self.allowed_roots:
			root_real = os.path.realpath(root)
			if target == root_real or target.startswith(root_real + os.sep):
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
		session = Session(
			sid,
			config,
			SessionLog(self._log_path(sid)),
			self.event_sink,
			self.credentials,
		)
		self._cache[sid] = session
		return session

	def exists(self, sid: str) -> bool:
		return sid in self._cache or os.path.isfile(self._meta_path(sid))


def _rebuild_messages(log: SessionLog) -> list[dict]:
	"""Reconstruct the LLM message transcript from durable log entries."""
	messages: list[dict] = []
	for raw in log.read_since(0):
		ev = parse_event(raw)
		if ev.type == "user_message":
			messages.append({"role": "user", "content": ev.content})
		elif ev.type == "assistant_message":
			msg: dict = {"role": "assistant", "content": ev.text or None}
			if ev.provider_data:
				msg["provider_data"] = ev.provider_data
			if ev.tool_calls:
				msg["tool_calls"] = [
					{
						"id": tc.id,
						"type": "function",
						"function": {"name": tc.name, "arguments": json.dumps(tc.args)},
					}
					for tc in ev.tool_calls
				]
			messages.append(msg)
		elif ev.type == "tool_result":
			messages.append({"role": "tool", "tool_call_id": ev.tool_call_id, "content": ev.content})
	return messages
