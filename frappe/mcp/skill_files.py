# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

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
		except OSError:
			raise McpError(INVALID_PARAMS, "Unknown skill resource") from None
		if len(content) > limit:
			raise McpError(INTERNAL_ERROR, "Skill exceeds the 16 MiB size limit", status=500)
		return content

	def paths(self, relative: Path = Path()) -> list[Path]:
		paths = []
		folder = self.root / relative
		if folder.is_symlink():
			return paths
		for directory, directories, files in folder.walk(follow_symlinks=False):
			directories[:] = sorted(name for name in directories if not (directory / name).is_symlink())
			paths.extend(
				(directory / name).relative_to(self.root)
				for name in sorted(files)
				if (directory / name).is_file() and not (directory / name).is_symlink()
			)
		return sorted(paths)

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
		directory = self._open_directory(stack, self.root)
		for part in relative.parts:
			directory = self._open_directory(stack, part, directory)
		return directory

	@staticmethod
	def _open_directory(stack: ExitStack, path: str | Path, parent: int | None = None) -> int:
		descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
		stack.callback(os.close, descriptor)
		return descriptor


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
