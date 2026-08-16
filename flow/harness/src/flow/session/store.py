"""Project-grouped session storage: private log/meta/attachment paths, the cwd fence,
and a process cache mapping each id to one live object."""

from __future__ import annotations

import asyncio
import builtins
import hashlib
import json
import os
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp

from flow import config as server_config
from flow.extensions import ExtensionRuntime, unload_extension_modules
from flow.model.credentials import CredentialStore
from flow.path_policy import canonical_path, is_path_allowed, normalize_roots
from flow.session.attachments import AttachmentStore
from flow.session.config import SessionConfig
from flow.session.log import SessionLog
from flow.session.prompt import build_system_prompt
from flow.session.session import Session, SessionConflict
from flow.session.skills import SkillCatalog, discover_skills, parse_skill_invocation
from flow.tools import Tool
from flow.tools.builtins import BUILTIN_TOOLS

# client-provided session ids land in on-disk filenames — keep them to a safe slug so a
# value like "../../etc/x" can't escape the sessions dir (arbitrary file write)
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_META_SUFFIX = ".meta.json"
_SKILLS_SUFFIX = ".skills.json"
_PROJECT_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")
_PROJECT_SLUG_LIMIT = 48
_PROJECT_HASH_LENGTH = 12


@dataclass(frozen=True)
class _SessionPaths:
	directory: str
	log: str
	meta: str
	skills: str
	attachments: str


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
		extension_paths: builtins.list[str] | None = None,
		extensions_enabled: bool = False,
	):
		self.data_dir = data_dir
		self.sessions_dir = os.path.join(data_dir, "sessions")
		_make_private_dir(self.data_dir)
		_make_private_dir(self.sessions_dir)
		self.event_sink = event_sink
		configured_roots = allowed_roots if allowed_roots is not None else server_config.ALLOWED_ROOTS
		self.allowed_roots = normalize_roots(configured_roots)
		self.credentials = credential_store or CredentialStore(server_config.CREDENTIALS_PATH)
		self._extension_paths = tuple(extension_paths or ())
		self._extensions_enabled = extensions_enabled
		self.extension_runtime = self._load_extensions()
		self._cache: dict[str, Session] = {}

	def _load_extensions(self) -> ExtensionRuntime:
		runtime = ExtensionRuntime()
		runtime.load(
			global_dir=Path(server_config.EXTENSIONS_PATH),
			extra_paths=tuple(Path(path) for path in self._extension_paths),
			include_global_dir=self._extensions_enabled,
		)
		return runtime

	def reload_extensions(self) -> None:
		"""Re-discover and re-import all extensions into a fresh runtime.

		Cached sessions get the recomposed tools for their next run; an active run
		keeps the tools it started with, and prompts stay as composed at creation.
		"""
		unload_extension_modules()
		self.extension_runtime = self._load_extensions()
		for session in list(self._cache.values()):
			session.server_tools = self._compose_tools(session.config)

	def create(self, config: SessionConfig) -> Session:
		self._validate_create_config(config)
		skill_catalog = self._discover_skills(config)
		return self._create_with_skills_catalog(config, skill_catalog)

	async def create_async(self, config: SessionConfig) -> Session:
		"""Create without blocking the server event loop during filesystem discovery."""
		self._validate_create_config(config)
		skill_catalog = await asyncio.to_thread(self._discover_skills, config)
		return self._create_with_skills_catalog(config, skill_catalog)

	async def preview_skill_catalog(self, config: SessionConfig) -> SkillCatalog:
		"""Discover the catalog for a lazy client without creating a session."""
		self._validate_create_config(config)
		return await asyncio.to_thread(self._discover_skills, config)

	def _validate_create_config(self, config: SessionConfig) -> None:
		self._validate_cwd(config.cwd)
		self._validate_skill_paths(config)

	def _discover_skills(self, config: SessionConfig) -> SkillCatalog:
		return discover_skills(
			config.cwd,
			enabled=config.skills_enabled,
			extra_paths=config.skill_paths,
			allowed_roots=self.allowed_roots,
		)

	def _compose_tools(self, config: SessionConfig) -> dict[str, Tool]:
		selected = {name: BUILTIN_TOOLS[name] for name in config.tools if name in BUILTIN_TOOLS}
		return self.extension_runtime.compose_tools(selected)

	def _create_with_skills_catalog(self, config: SessionConfig, skill_catalog: SkillCatalog) -> Session:
		# Catalog metadata and the composed prompt are immutable for this session.
		# Skill files themselves remain live and are read when used, matching Pi.
		server_tools = self._compose_tools(config)
		config = config.model_copy(
			update={
				"system_prompt": build_system_prompt(
					config,
					skills=skill_catalog.skills,
					tools=tuple(server_tools.values()),
				)
			}
		)
		sid = config.session_id or uuid.uuid4().hex[:16]
		if not _SID_RE.match(sid):
			raise ValueError(f"invalid session_id {sid!r} (allowed: letters, digits, - _)")
		if self.exists(sid):
			raise ValueError(f"session_id {sid!r} already exists")
		paths = self._project_paths(sid, config.cwd)
		_make_private_dir(paths.directory)
		session = self._build(sid, config, paths, skill_catalog=skill_catalog, server_tools=server_tools)
		self._save_catalog(paths, skill_catalog)
		self.save_meta(session)
		self._cache[sid] = session
		return session

	def get(self, sid: str) -> Session:
		if sid in self._cache:
			return self._cache[sid]
		paths = self._locate(sid)
		if paths is None:
			raise KeyError(sid)
		with open(paths.meta, encoding="utf-8") as f:
			config = SessionConfig.model_validate(json.load(f))
		self._validate_cwd(config.cwd)
		self._validate_skill_paths(config)
		session = self._build(
			sid,
			config,
			paths,
			skill_catalog=self._load_catalog(paths),
			server_tools=self._compose_tools(config),
		)
		self._cache[sid] = session
		return session

	def exists(self, sid: str) -> bool:
		return sid in self._cache or self._locate(sid) is not None

	def title(self, sid: str) -> str | None:
		"""The session's display title: the generated title when one exists, else its
		first user message read from the log head (the durable row — a compaction's
		synthetic summary never replaces it)."""
		session = self._cache.get(sid)
		if session is not None:
			return session.config.title or _read_first_user_message(session.log.path)
		paths = self._locate(sid)
		if paths is None:
			return None
		try:
			with open(paths.meta, encoding="utf-8") as file:
				config = SessionConfig.model_validate(json.load(file))
		except (OSError, ValueError):
			return _read_first_user_message(paths.log)
		return config.title or _read_first_user_message(paths.log)

	def delete(self, sid: str) -> None:
		"""Remove every session artifact, then its empty project directory.

		Deletion is refused while the run is active. Attachment cleanup happens first,
		so a filesystem failure cannot leave unaddressable bytes after meta deletion.
		"""
		session = self._cache.get(sid)
		paths = (
			_session_paths(os.path.dirname(session.log.path), sid)
			if session is not None
			else self._locate(sid)
		)
		if paths is None:
			raise KeyError(sid)
		if session is not None and session.is_running:
			raise SessionConflict("cannot delete a session with an active run")
		if session is not None:
			session.cancel_titling()  # a late title write must not resurrect the meta file
		attachment_store = session.attachment_store if session is not None else None
		if attachment_store is not None:
			attachment_store.remove_all()
		elif os.path.exists(paths.attachments):
			AttachmentStore(paths.attachments).remove_all()
		for path in (paths.log, paths.meta, paths.skills):
			try:
				os.unlink(path)
			except FileNotFoundError:
				pass
		self._cache.pop(sid, None)
		if paths.directory != self.sessions_dir:
			try:
				os.rmdir(paths.directory)
			except OSError:
				pass  # another session (or an operator-owned file) still uses the project

	def list(self) -> builtins.list[SessionInfo]:
		"""Cheap listing for pickers, newest activity first. Sessions with no durable
		entries are omitted — there is nothing to resume. Cached sessions report live
		values; cold sessions are read from their meta file and log tail only (no log
		replay), so a cold session's model can lag a later `model_changed` row — use
		`get` for exact values."""
		items: builtins.list[tuple[float, SessionInfo]] = []
		seen: set[str] = set()
		for paths in self._iter_session_paths():
			sid = os.path.basename(paths.meta)[: -len(_META_SUFFIX)]
			if sid in seen:
				continue
			seen.add(sid)
			info = self._describe(sid, paths)
			if info is None or info.latest_seq == 0:
				continue
			try:
				mtime = os.path.getmtime(paths.log if os.path.isfile(paths.log) else paths.meta)
			except OSError:
				mtime = 0.0
			items.append((mtime, info))
		items.sort(key=lambda item: item[0], reverse=True)
		return [info for _, info in items]

	def _describe(self, sid: str, paths: _SessionPaths) -> SessionInfo | None:
		session = self._cache.get(sid)
		if session is not None:
			return SessionInfo(
				session_id=sid,
				state=session.state.value,
				model=session.model,
				latest_seq=session.log.latest_seq,
				cwd=session.config.cwd,
				title=session.config.title or _read_first_user_message(session.log.path),
			)
		try:
			with open(paths.meta, encoding="utf-8") as f:
				config = SessionConfig.model_validate(json.load(f))
		except (OSError, ValueError):
			return None  # one broken meta file must not break the whole listing
		tail = _read_last_row(paths.log)
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
			title=config.title or _read_first_user_message(paths.log),
		)

	def save_meta(self, session: Session) -> None:
		"""Write the session's config to its meta file (called at create and on config
		patches like `auto_approve`; model changes live in the log instead)."""
		paths = _session_paths(os.path.dirname(session.log.path), session.id)
		path = paths.meta
		fd, tmp = mkstemp(prefix=f".{os.path.basename(path)}.", dir=paths.directory)
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as f:
				json.dump(session.config.model_dump(), f)
			os.replace(tmp, path)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)

	def _build(
		self,
		sid: str,
		config: SessionConfig,
		paths: _SessionPaths,
		*,
		skill_catalog: SkillCatalog,
		server_tools: dict[str, Tool],
	) -> Session:
		return Session(
			sid,
			config,
			SessionLog(paths.log),
			event_sink=self.event_sink,
			credentials=self.credentials,
			allowed_roots=self.allowed_roots,
			attachment_store=AttachmentStore(paths.attachments),
			skill_catalog=skill_catalog,
			server_tools=server_tools,
			persist_meta=self.save_meta,
		)

	def _save_catalog(self, paths: _SessionPaths, skill_catalog: SkillCatalog) -> None:
		fd, tmp = mkstemp(prefix=f".{os.path.basename(paths.skills)}.", dir=paths.directory)
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as file:
				json.dump(skill_catalog.model_dump(mode="json"), file)
			os.replace(tmp, paths.skills)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)

	def _load_catalog(self, paths: _SessionPaths) -> SkillCatalog:
		try:
			with open(paths.skills, encoding="utf-8") as file:
				skill_catalog = SkillCatalog.model_validate(json.load(file))
		except FileNotFoundError:
			return SkillCatalog()  # sessions created before skills support
		self._validate_catalog(skill_catalog)
		return skill_catalog

	def _validate_catalog(self, skill_catalog: SkillCatalog) -> None:
		"""Do not let a persisted catalog outlive a tightened filesystem fence."""
		if not self.allowed_roots:
			return
		global_root = canonical_path(os.path.join(os.path.expanduser("~"), ".agents", "skills"))
		roots = (global_root, *self.allowed_roots)
		for skill in skill_catalog.skills:
			if not is_path_allowed(skill.canonical_path, roots):
				raise ValueError(f"stored skill {skill.name!r} is outside allowed roots")

	def _project_paths(self, sid: str, cwd: str) -> _SessionPaths:
		directory = os.path.join(self.sessions_dir, _project_directory_name(cwd))
		return _session_paths(directory, sid)

	def _locate(self, sid: str) -> _SessionPaths | None:
		if not _SID_RE.match(sid):
			return None
		for entry in os.scandir(self.sessions_dir):
			if entry.name.startswith(".") or not entry.is_dir(follow_symlinks=False):
				continue
			paths = _session_paths(entry.path, sid)
			if os.path.isfile(paths.meta):
				return paths
		return None

	def _iter_session_paths(self) -> Iterator[_SessionPaths]:
		for entry in os.scandir(self.sessions_dir):
			if entry.name.startswith(".") or not entry.is_dir(follow_symlinks=False):
				continue
			for child in os.scandir(entry.path):
				if child.is_file(follow_symlinks=False) and child.name.endswith(_META_SUFFIX):
					sid = child.name[: -len(_META_SUFFIX)]
					if _SID_RE.match(sid):
						yield _session_paths(entry.path, sid)

	def _validate_skill_paths(self, config: SessionConfig) -> None:
		"""Explicit skill paths are client input and obey the normal filesystem fence."""
		for raw in config.skill_paths:
			value = raw.strip()
			if not value:
				raise ValueError("skill_paths entries must not be empty")
			if not self.allowed_roots:
				continue
			expanded = os.path.expanduser(value)
			path = expanded if os.path.isabs(expanded) else os.path.join(config.cwd, expanded)
			if not is_path_allowed(canonical_path(path), self.allowed_roots):
				raise ValueError(f"skill path {raw!r} is not under an allowed root")

	def _validate_cwd(self, cwd: str) -> None:
		"""Fence a session's cwd to `allowed_roots` (realpath-resolved, so symlink/`..`
		escapes can't slip past). Empty roots = unrestricted (dev default)."""
		if not self.allowed_roots:
			return
		if not is_path_allowed(canonical_path(cwd), self.allowed_roots):
			raise ValueError(f"cwd {cwd!r} is not under an allowed root")


def _project_directory_name(cwd: str) -> str:
	canonical = canonical_path(cwd)
	basename = os.path.basename(os.path.normpath(canonical)) or "root"
	slug = _PROJECT_SLUG_RE.sub("-", basename).strip(".-_")[:_PROJECT_SLUG_LIMIT] or "project"
	digest = hashlib.sha256(os.fsencode(os.path.normcase(canonical))).hexdigest()[:_PROJECT_HASH_LENGTH]
	return f"{slug}--{digest}"


def _session_paths(directory: str, sid: str) -> _SessionPaths:
	return _SessionPaths(
		directory=directory,
		log=os.path.join(directory, f"{sid}.jsonl"),
		meta=os.path.join(directory, f"{sid}.meta.json"),
		skills=os.path.join(directory, f"{sid}{_SKILLS_SUFFIX}"),
		attachments=os.path.join(directory, f"{sid}.attachments"),
	)


def _read_first_user_message(path: str) -> str | None:
	"""First line of the log's first user_message row, from a bounded head read."""
	try:
		with open(path, encoding="utf-8") as file:
			head = file.read(65536)
	except OSError:
		return None
	for line in head.splitlines():
		try:
			row = json.loads(line)
		except json.JSONDecodeError:
			continue  # the head cut may tear the last line
		if isinstance(row, dict) and row.get("type") == "user_message":
			return _user_message_title(row)
	return None


def _user_message_title(row: dict) -> str | None:
	content = row.get("content", "")
	if isinstance(content, list):
		blocks = content
		content = "".join(
			str(block.get("text", ""))
			for block in blocks
			if isinstance(block, dict) and block.get("type") == "text"
		)
		if not str(content).strip():
			content = next(
				(
					str(block.get("name", ""))
					for block in blocks
					if isinstance(block, dict) and block.get("type") == "attachment"
				),
				"",
			)
	text = str(content).strip()
	invocation = parse_skill_invocation(text)
	if invocation is not None:
		text = invocation.instructions or f"/skill:{invocation.name}"
	first = text.split("\n")[0]
	return first[:120] or None


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
