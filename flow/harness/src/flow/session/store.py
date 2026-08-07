"""Where sessions live on disk: private directories, the log and meta files, the cwd
fence, and a per-process cache so one session id maps to one live object."""

from __future__ import annotations

import builtins
import json
import os
import re
import uuid
from dataclasses import dataclass
from tempfile import mkstemp

from flow import config as server_config
from flow.model.credentials import CredentialStore
from flow.path_policy import canonical_path, is_path_allowed, normalize_roots
from flow.session.config import SessionConfig
from flow.session.log import SessionLog
from flow.session.prompt import build_system_prompt
from flow.session.session import Session, SessionConflict

# client-provided session ids land in on-disk filenames — keep them to a safe slug so a
# value like "../../etc/x" can't escape the sessions dir (arbitrary file write)
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_META_SUFFIX = ".meta.json"


@dataclass(frozen=True)
class SessionInfo:
	"""One row of `SessionStore.list()` — enough for a session picker."""

	session_id: str
	state: str
	model: str
	latest_seq: int
	cwd: str
	title: str | None = None


class SessionStore:
	def __init__(
		self,
		data_dir: str,
		event_sink=None,
		allowed_roots: builtins.list[str] | None = None,
		credential_store: CredentialStore | None = None,
	):
		self.data_dir = data_dir
		self.sessions_dir = os.path.join(data_dir, "sessions")
		_make_private_dir(self.data_dir)
		_make_private_dir(self.sessions_dir)
		self.event_sink = event_sink
		configured_roots = allowed_roots if allowed_roots is not None else server_config.ALLOWED_ROOTS
		self.allowed_roots = normalize_roots(configured_roots)
		self.credentials = credential_store or CredentialStore(server_config.CREDENTIALS_PATH)
		self._cache: dict[str, Session] = {}

	def create(self, config: SessionConfig) -> Session:
		self._validate_cwd(config.cwd)
		# compose once, here; the meta file persists the resolved prompt, so later
		# AGENTS.md edits never leak into an existing session
		config = config.model_copy(update={"system_prompt": build_system_prompt(config)})
		sid = config.session_id or uuid.uuid4().hex[:16]
		if not _SID_RE.match(sid):
			raise ValueError(f"invalid session_id {sid!r} (allowed: letters, digits, - _)")
		session = self._build(sid, config)
		self.save_meta(session)
		self._cache[sid] = session
		return session

	def get(self, sid: str) -> Session:
		if sid in self._cache:
			return self._cache[sid]
		meta_path = self._meta_path(sid)
		if not os.path.isfile(meta_path):
			raise KeyError(sid)
		with open(meta_path, encoding="utf-8") as f:
			config = SessionConfig.model_validate(json.load(f))
		self._validate_cwd(config.cwd)
		session = self._build(sid, config)
		self._cache[sid] = session
		return session

	def exists(self, sid: str) -> bool:
		return sid in self._cache or os.path.isfile(self._meta_path(sid))

	def title(self, sid: str) -> str | None:
		"""The session's display title: its first user message, read from the log head
		(the durable row — a compaction's synthetic summary never replaces it)."""
		return _read_first_user_message(self._log_path(sid))

	def delete(self, sid: str) -> None:
		"""Remove a session's log and meta files. Refused while its run is active."""
		if not _SID_RE.match(sid) or not self.exists(sid):
			raise KeyError(sid)
		session = self._cache.get(sid)
		if session is not None and session.is_running:
			raise SessionConflict("cannot delete a session with an active run")
		self._cache.pop(sid, None)
		for path in (self._log_path(sid), self._meta_path(sid)):
			try:
				os.unlink(path)
			except FileNotFoundError:
				pass

	def list(self) -> builtins.list[SessionInfo]:
		"""Cheap listing for pickers, newest activity first. Sessions with no durable
		entries are omitted — there is nothing to resume. Cached sessions report live
		values; cold sessions are read from their meta file and log tail only (no log
		replay), so a cold session's model can lag a later `model_changed` row — use
		`get` for exact values."""
		items: builtins.list[tuple[float, SessionInfo]] = []
		for name in os.listdir(self.sessions_dir):
			if name.startswith(".") or not name.endswith(_META_SUFFIX):
				continue
			sid = name[: -len(_META_SUFFIX)]
			info = self._describe(sid)
			if info is None or info.latest_seq == 0:
				continue
			log_path = self._log_path(sid)
			try:
				mtime = os.path.getmtime(log_path if os.path.isfile(log_path) else self._meta_path(sid))
			except OSError:
				mtime = 0.0
			items.append((mtime, info))
		items.sort(key=lambda item: item[0], reverse=True)
		return [info for _, info in items]

	def _describe(self, sid: str) -> SessionInfo | None:
		session = self._cache.get(sid)
		if session is not None:
			return SessionInfo(
				session_id=sid,
				state=session.state.value,
				model=session.model,
				latest_seq=session.log.latest_seq,
				cwd=session.config.cwd,
				title=self.title(sid),
			)
		try:
			with open(self._meta_path(sid), encoding="utf-8") as f:
				config = SessionConfig.model_validate(json.load(f))
		except (OSError, ValueError):
			return None  # one broken meta file must not break the whole listing
		tail = _read_last_row(self._log_path(sid))
		latest_seq = tail.get("seq") if tail else 0
		if not isinstance(latest_seq, int):
			latest_seq = 0
		# A paused run's final durable row is run_ended(paused); resume, cancel_pending,
		# and rewind all append past it, so the tail row is a faithful paused test.
		paused = tail is not None and tail.get("type") == "run_ended" and tail.get("reason") == "paused"
		return SessionInfo(
			session_id=sid,
			state="paused" if paused else "idle",
			model=config.model,
			latest_seq=latest_seq,
			cwd=config.cwd,
			title=self.title(sid),
		)

	def save_meta(self, session: Session) -> None:
		"""Write the session's config to its meta file (called at create and on config
		patches like `auto_approve`; model changes live in the log instead)."""
		path = self._meta_path(session.id)
		fd, tmp = mkstemp(prefix=f".{os.path.basename(path)}.", dir=self.sessions_dir)
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				json.dump(session.config.model_dump(), f)
			os.replace(tmp, path)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)

	def _build(self, sid: str, config: SessionConfig) -> Session:
		return Session(
			sid,
			config,
			SessionLog(self._log_path(sid)),
			event_sink=self.event_sink,
			credentials=self.credentials,
			allowed_roots=self.allowed_roots,
		)

	def _log_path(self, sid: str) -> str:
		return os.path.join(self.sessions_dir, f"{sid}.jsonl")

	def _meta_path(self, sid: str) -> str:
		return os.path.join(self.sessions_dir, f"{sid}.meta.json")

	def _validate_cwd(self, cwd: str) -> None:
		"""Fence a session's cwd to `allowed_roots` (realpath-resolved, so symlink/`..`
		escapes can't slip past). Empty roots = unrestricted (dev default)."""
		if not self.allowed_roots:
			return
		if not is_path_allowed(canonical_path(cwd), self.allowed_roots):
			raise ValueError(f"cwd {cwd!r} is not under an allowed root")


def _read_first_user_message(path: str) -> str | None:
	"""First line of the log's first user_message row, from a bounded head read."""
	try:
		with open(path, encoding="utf-8") as f:
			head = f.read(65536)
	except OSError:
		return None
	for line in head.splitlines():
		try:
			row = json.loads(line)
		except json.JSONDecodeError:
			continue  # the head cut may tear the last line
		if isinstance(row, dict) and row.get("type") == "user_message":
			first = str(row.get("content", "")).strip().split("\n")[0]
			return first[:120] or None
	return None


def _read_last_row(path: str) -> dict | None:
	"""The last complete JSON row of an append-only log, read from the tail without
	parsing the whole file. Returns None for a missing, empty, or unreadable tail."""
	try:
		size = os.path.getsize(path)
		if size == 0:
			return None
		block = 65536
		with open(path, "rb") as f:
			while True:
				start = max(0, size - block)
				f.seek(start)
				data = f.read()
				# enough context once the block holds a full line boundary or the file start
				if start == 0 or data.count(b"\n") > 1:
					break
				block *= 2
	except OSError:
		return None
	for line in reversed([line for line in data.splitlines() if line.strip()]):
		try:
			row = json.loads(line)
		except json.JSONDecodeError:
			continue  # a torn final line; the row before it is the durable tail
		if isinstance(row, dict):
			return row
	return None


def _make_private_dir(path: str) -> None:
	existed = os.path.isdir(path)
	os.makedirs(path, mode=0o700, exist_ok=True)
	if not existed:
		os.chmod(path, 0o700)
