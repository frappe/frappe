"""Where sessions live on disk: private directories, the log and meta files, the cwd
fence, and a per-process cache so one session id maps to one live object."""

from __future__ import annotations

import json
import os
import re
import uuid
from tempfile import mkstemp

from flow_server import config as server_config
from flow_server.model.credentials import CredentialStore
from flow_server.path_policy import canonical_path, is_path_allowed, normalize_roots
from flow_server.session.config import SessionConfig
from flow_server.session.log import SessionLog
from flow_server.session.session import Session

# client-provided session ids land in on-disk filenames — keep them to a safe slug so a
# value like "../../etc/x" can't escape the sessions dir (arbitrary file write)
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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
		_make_private_dir(self.data_dir)
		_make_private_dir(self.sessions_dir)
		self.event_sink = event_sink
		configured_roots = allowed_roots if allowed_roots is not None else server_config.ALLOWED_ROOTS
		self.allowed_roots = normalize_roots(configured_roots)
		self.credentials = credential_store or CredentialStore(server_config.CREDENTIALS_PATH)
		self._cache: dict[str, Session] = {}

	def create(self, config: SessionConfig) -> Session:
		self._validate_cwd(config.cwd)
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

	def save_meta(self, session: Session) -> None:
		"""Write the session's config to its meta file (config is fixed after create;
		later model changes live in the log)."""
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


def _make_private_dir(path: str) -> None:
	existed = os.path.isdir(path)
	os.makedirs(path, mode=0o700, exist_ok=True)
	if not existed:
		os.chmod(path, 0o700)
