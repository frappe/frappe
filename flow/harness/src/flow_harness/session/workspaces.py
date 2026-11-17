"""Workspaces: the folders the web UI groups chats under, each with a name of its own.

Kept in `<data_dir>/workspaces.json`, one per folder. The first listing adds the folder of
every chat so far, or a default folder when there are none; after that a chat's first
message adds its folder's."""

from __future__ import annotations

import builtins
import json
import logging
import os
import threading
from collections.abc import Callable, Iterable
from tempfile import mkstemp

from flow_harness.path_policy import canonical_path, is_path_allowed

# made by the first listing when there are no chats yet
DEFAULT_WORKSPACE = os.path.join("~", "flow", "default-workspace")


class WorkspaceRegistry:
	"""`{"path", "name"}` rows, oldest first. Paths are canonical, so a folder reached
	through a symlink is the same workspace."""

	def __init__(self, path: str, *, allowed_roots: tuple[str, ...], folders: Callable[[], Iterable[str]]):
		self.path = path
		self.allowed_roots = allowed_roots
		self._folders = folders  # the chats' folders, newest first
		self._lock = threading.Lock()

	def list(self) -> builtins.list[dict]:
		with self._lock:
			return self._load()

	def paths(self) -> set[str]:
		"""Every workspace's folder; none before the first listing."""
		return {workspace["path"] for workspace in self._read() or ()}

	def add(self, folder: str) -> dict:
		"""An existing folder's workspace, added if it has none."""
		path = canonical_path(folder)
		if not os.path.isabs(folder) or not os.path.isdir(path):
			raise ValueError(f"{folder!r} is not an absolute path to a folder")
		if self.allowed_roots and not is_path_allowed(path, self.allowed_roots):
			raise ValueError(f"{folder!r} is not under an allowed root")
		with self._lock:
			workspaces = self._load()
			if _add(workspaces, path):
				self._write(workspaces)
			return next(workspace for workspace in workspaces if workspace["path"] == path)

	def ensure(self, folder: str) -> None:
		"""Add a chat's folder, once the list exists."""
		with self._lock:
			workspaces = self._read()
			if workspaces is None or not _add(workspaces, folder):
				return
			try:
				self._write(workspaces)
			except OSError as error:  # the chat goes on without it
				logging.getLogger("flow").warning("cannot add the workspace of %s: %s", folder, error)

	def rename(self, path: str, name: str) -> dict | None:
		with self._lock:
			workspaces = self._read() or []
			workspace = next((workspace for workspace in workspaces if workspace["path"] == path), None)
			if workspace is not None:
				workspace["name"] = name
				self._write(workspaces)
			return workspace

	def remove(self, path: str) -> bool:
		"""Off the list only: the folder and its chats stay."""
		with self._lock:
			workspaces = self._read() or []
			kept = [workspace for workspace in workspaces if workspace["path"] != path]
			if len(kept) == len(workspaces):
				return False
			self._write(kept)
			return True

	def _load(self) -> builtins.list[dict]:
		workspaces = self._read()
		if workspaces is None:
			workspaces = []
			for folder in reversed(list(self._folders())):
				_add(workspaces, folder)
			if not workspaces and (default := self._default()):
				_add(workspaces, default)
			self._write(workspaces)
		return workspaces

	def _default(self) -> str | None:
		"""The default folder, made if missing; None outside the allowed roots."""
		path = os.path.expanduser(DEFAULT_WORKSPACE)
		if self.allowed_roots and not is_path_allowed(canonical_path(path), self.allowed_roots):
			return None
		try:
			os.makedirs(path, exist_ok=True)
		except OSError:
			return None
		return path

	def _read(self) -> builtins.list[dict] | None:
		"""None before the first listing, or when the file can't be read, so it's made again."""
		try:
			with open(self.path, encoding="utf-8") as file:
				data = json.load(file)
		except (OSError, ValueError):
			return None
		return data if isinstance(data, list) else None

	def _write(self, workspaces: builtins.list[dict]) -> None:
		fd, tmp = mkstemp(prefix=".workspaces.", dir=os.path.dirname(self.path))
		try:
			os.chmod(tmp, 0o600)
			with os.fdopen(fd, "w", encoding="utf-8") as file:
				json.dump(workspaces, file)
			os.replace(tmp, self.path)
		finally:
			if os.path.exists(tmp):
				os.unlink(tmp)


def _add(workspaces: list[dict], folder: str) -> bool:
	"""Add the folder's workspace, named after it, unless it has one."""
	path = canonical_path(folder)
	if any(workspace["path"] == path for workspace in workspaces):
		return False
	workspaces.append({"path": path, "name": os.path.basename(path) or path})
	return True
