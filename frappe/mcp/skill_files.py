# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import errno
import json
import os
import re
import stat
from contextlib import ExitStack
from pathlib import Path

import yaml

from frappe.mcp.protocol import INTERNAL_ERROR, INVALID_PARAMS, McpError

MAX_SKILL_FILES = 512
MAX_SKILL_BYTES = 16 * 1024 * 1024
FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_UNKNOWN_PATH_ERRORS = (errno.ENOENT, errno.ENOTDIR, errno.ELOOP)


class SkillFiles:
	def __init__(self, root: Path) -> None:
		self.root = root

	def read(self, relative: Path, limit: int = MAX_SKILL_BYTES) -> bytes:
		"""Read regular files without following symlinks in any skills directory component."""
		try:
			with ExitStack() as stack:
				directory = self._directory(stack, relative.parent)
				descriptor = os.open(
					relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
				)
				with os.fdopen(descriptor, "rb") as file:
					if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
						raise McpError(INVALID_PARAMS, "Unknown skill resource")
					content = file.read(limit + 1)
		except OSError as error:
			if error.errno not in _UNKNOWN_PATH_ERRORS:
				raise
			raise McpError(INVALID_PARAMS, "Unknown skill resource") from None
		if len(content) > limit:
			raise McpError(INTERNAL_ERROR, "Skill exceeds the 16 MiB size limit", status=500)
		return content

	def children(self, relative: Path) -> list[tuple[Path, bool]]:
		try:
			with ExitStack() as stack:
				directory = self._directory(stack, relative)
				children = []
				for name in os.listdir(directory):
					if is_hidden(Path(name)):
						continue
					mode = os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode
					if stat.S_ISREG(mode) or stat.S_ISDIR(mode):
						children.append((relative / name, stat.S_ISDIR(mode)))
				return children
		except OSError as error:
			if error.errno not in _UNKNOWN_PATH_ERRORS:
				raise
			raise McpError(INVALID_PARAMS, "Unknown skill directory") from None

	def paths(self, relative: Path = Path()) -> list[Path]:
		paths = []
		folder = self.root / relative
		try:
			mode = folder.lstat().st_mode
		except FileNotFoundError:
			if relative.parts:
				raise
			return paths
		if stat.S_ISLNK(mode):
			return paths
		for directory, directories, files in folder.walk(follow_symlinks=False, on_error=raise_scan_error):
			directories[:] = [
				name
				for name in directories
				if not is_hidden(Path(name)) and not stat.S_ISLNK((directory / name).lstat().st_mode)
			]
			paths.extend(
				(directory / name).relative_to(self.root)
				for name in files
				if not is_hidden(Path(name)) and stat.S_ISREG((directory / name).lstat().st_mode)
			)
		return paths

	def frontmatter(self, relative: Path, content: bytes | None = None) -> dict:
		try:
			match = FRONTMATTER.match((self.read(relative) if content is None else content).decode("utf-8"))
			if match is None:
				raise ValueError("SKILL.md requires YAML frontmatter")
			metadata = yaml.safe_load(match.group(1))
			validate_frontmatter(metadata, relative.parent.name)
			if json.loads(json.dumps(metadata, allow_nan=False)) != metadata:
				raise ValueError("frontmatter must contain JSON-compatible values")
		except (ValueError, TypeError, yaml.YAMLError) as error:
			raise McpError(INTERNAL_ERROR, "Invalid app skill: {0}".format(error), status=500) from None
		return metadata

	def _directory(self, stack: ExitStack, relative: Path) -> int:
		directory = None
		for part in (self.root, *relative.parts):
			directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
			stack.callback(os.close, directory)
		return directory


def raise_scan_error(error: OSError) -> None:
	raise error


def is_hidden(path: Path) -> bool:
	return any(part.startswith(".") for part in path.parts)


def path_mode(path: Path) -> int:
	try:
		return path.lstat().st_mode
	except OSError as error:
		if error.errno not in _UNKNOWN_PATH_ERRORS:
			raise
		return 0


def validate_frontmatter(metadata: dict, directory_name: str) -> None:
	if not isinstance(metadata, dict) or not all(isinstance(key, str) for key in metadata):
		raise ValueError("frontmatter must be an object with string keys")
	name = metadata.get("name")
	if not isinstance(name, str) or len(name) > 64 or not SKILL_NAME.fullmatch(name):
		raise ValueError("invalid skill name")
	if name != directory_name:
		raise ValueError("skill name must match its directory")
	for field, maximum in (("description", 1024), ("compatibility", 500)):
		if field == "description" or field in metadata:
			value = metadata.get(field)
			if not isinstance(value, str) or not value.strip() or len(value) > maximum:
				raise ValueError(f"{field} must contain 1 to {maximum} characters")
	for field in ("license", "allowed-tools"):
		if field in metadata and not isinstance(metadata[field], str):
			raise ValueError(f"{field} must be a string")
	if "metadata" in metadata:
		values = metadata["metadata"]
		if not isinstance(values, dict) or not all(
			isinstance(key, str) and isinstance(value, str) for key, value in values.items()
		):
			raise ValueError("metadata must map strings to strings")
