# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Publish installed apps' skills/ files under skill://<app>/<path> without executing them."""

import base64
import binascii
import hashlib
import mimetypes
import stat
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import frappe
from frappe.mcp.protocol import INTERNAL_ERROR, INVALID_PARAMS, McpError
from frappe.mcp.skill_files import MAX_SKILL_BYTES, MAX_SKILL_FILES, SkillFiles, is_hidden, path_mode

SKILLS_EXTENSION = "io.modelcontextprotocol/skills"
PAGE_SIZE = 50


class SkillCatalog:
	def __init__(self) -> None:
		self.apps = {
			app: SkillFiles(Path(frappe.get_app_source_path(app, "skills")))
			for app in frappe.get_installed_apps(_ensure_on_bench=True)
		}

	def list_skills(self, cursor: str | None = None) -> dict:
		paths = {resource_uri(app, path): (app, path) for app, path in self.skill_paths()}
		result = page([{"uri": uri} for uri in paths], "skills", cursor, "skills/list")
		manifest = _SkillManifest(self.apps)
		result["skills"] = [manifest.entry(*paths[item["uri"]]) for item in result["skills"]]
		return result

	def get_skill(self, uri: str) -> dict:
		app, path = self.location(uri)
		if path.name != "SKILL.md" or len(path.parts) < 2:
			raise McpError(INVALID_PARAMS, "Expected a skill's SKILL.md URI")
		return {"skill": _SkillManifest(self.apps).entry(app, path), **cache_policy()}

	def read_resource(self, uri: str) -> dict:
		app, path = self.location(uri)
		if not self.owner(app, path.parent):
			raise McpError(INVALID_PARAMS, "Unknown skill resource")
		content = self.apps[app].read(path)
		resource = {"uri": uri, "mimeType": mime_type(path)}
		try:
			resource["text"] = content.decode("utf-8")
		except UnicodeDecodeError:
			resource["blob"] = base64.b64encode(content).decode("ascii")
		return {"contents": [resource], **cache_policy()}

	def read_directory(self, uri: str, cursor: str | None = None) -> dict:
		app, path = self.location(uri)
		folder = self.apps[app].root / path
		if not stat.S_ISDIR(path_mode(folder)):
			raise McpError(INVALID_PARAMS, "Unknown skill directory")
		if self.owner(app, path):
			resources = [
				self.metadata(app, child, is_directory)
				for child, is_directory in self.apps[app].children(path)
			]
		else:
			children = set()
			for _, skill in self.skill_paths(app):
				if skill.is_relative_to(path) and len(skill.parts) > len(path.parts) + 1:
					children.add(Path(*skill.parts[: len(path.parts) + 1]))
			if not children:
				raise McpError(INVALID_PARAMS, "Unknown skill directory")
			resources = [self.metadata(app, child, True) for child in children]
		return page(resources, "resources", cursor, uri)

	def skill_paths(self, app: str | None = None) -> Iterator[tuple[str, Path]]:
		app_names = [app] if app else self.apps
		for app_name in sorted(app_names):
			for path in self.apps[app_name].paths():
				if path.name == "SKILL.md" and len(path.parts) >= 2:
					yield app_name, path

	def metadata(self, app: str, path: Path, is_directory: bool = False) -> dict:
		resource = {"uri": resource_uri(app, path), "name": path.name}
		if is_directory:
			resource["mimeType"] = "inode/directory"
		else:
			resource["mimeType"] = mime_type(path)
			if path.name == "SKILL.md":
				metadata = self.apps[app].frontmatter(path)
				resource.update(name=metadata["name"], description=metadata["description"])
		return resource

	def owner(self, app: str, directory: Path) -> Path | None:
		for length in range(1, len(directory.parts) + 1):
			parent = Path(*directory.parts[:length])
			if stat.S_ISREG(path_mode(self.apps[app].root / parent / "SKILL.md")):
				return parent
		return None

	def location(self, uri: str) -> tuple[str, Path]:
		if not isinstance(uri, str):
			raise McpError(INVALID_PARAMS, "A skill URI is required")
		try:
			parsed = urlsplit(uri)
			path = unquote(parsed.path, errors="strict")
		except ValueError:
			raise McpError(INVALID_PARAMS, "Invalid skill URI") from None
		parts = path.removeprefix("/").split("/") if path else []
		if (
			parsed.scheme != "skill"
			or parsed.netloc not in self.apps
			or parsed.query
			or parsed.fragment
			or any(part in ("", ".", "..") or "\x00" in part for part in parts)
		):
			raise McpError(INVALID_PARAMS, "Invalid skill URI")
		relative = Path(*parts)
		if is_hidden(relative):
			raise McpError(INVALID_PARAMS, "Unknown skill resource")
		if resource_uri(parsed.netloc, relative) != uri:
			raise McpError(INVALID_PARAMS, "Skill URI must use its canonical encoding")
		root = self.apps[parsed.netloc].root
		if stat.S_ISLNK(path_mode(root)) or any(
			stat.S_ISLNK(path_mode(root / Path(*parts[:end]))) for end in range(1, len(parts) + 1)
		):
			raise McpError(INVALID_PARAMS, "Unknown skill resource")
		return parsed.netloc, relative


class _SkillManifest:
	"""Share file records within one catalog operation without retaining file contents."""

	def __init__(self, apps: dict[str, SkillFiles]) -> None:
		self.apps = apps
		self.file_records: dict[tuple[str, Path], dict] = {}

	def entry(self, app: str, path: Path) -> dict:
		files = self.apps[app]
		skill_content = files.read(path)
		frontmatter = files.frontmatter(path, skill_content)
		paths = sorted(set(files.paths(path.parent)) | {path})
		if len(paths) > MAX_SKILL_FILES:
			raise McpError(INTERNAL_ERROR, "Skill exceeds the 512 file limit", status=500)
		resources = []
		total = 0
		for resource in paths:
			key = (app, resource)
			if key not in self.file_records:
				content = skill_content if resource == path else files.read(resource, MAX_SKILL_BYTES - total)
				self.file_records[key] = {
					"uri": resource_uri(app, resource),
					"digest": "sha256:" + hashlib.sha256(content).hexdigest(),
					"size": len(content),
				}
			record = self.file_records[key]
			total += record["size"]
			if total > MAX_SKILL_BYTES:
				raise McpError(INTERNAL_ERROR, "Skill exceeds the 16 MiB size limit", status=500)
			resources.append(record)
		return {"uri": resource_uri(app, path), "frontmatter": frontmatter, "resources": resources}


def resource_uri(app: str, path: Path) -> str:
	return "skill://" + app + ("/" + quote(path.as_posix(), safe="/") if path.parts else "")


def mime_type(path: Path) -> str:
	if path.suffix.lower() == ".md":
		return "text/markdown"
	return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def cache_policy() -> dict:
	return {"ttlMs": 0, "cacheScope": "private"}


def page(items: list[dict], field: str, cursor: str | None, scope: str) -> dict:
	items = sorted(items, key=lambda item: item["uri"])
	start = 0
	if cursor is not None:
		try:
			decoded = base64.b64decode(cursor, validate=True).decode("utf-8")
			prefix, after = decoded.split("\n", 1)
			if prefix != scope:
				raise ValueError
			start = [item["uri"] for item in items].index(after) + 1
		except (ValueError, TypeError, binascii.Error):
			raise McpError(INVALID_PARAMS, "Invalid pagination cursor") from None
	result = {field: items[start : start + PAGE_SIZE], **cache_policy()}
	if start + PAGE_SIZE < len(items):
		last = result[field][-1]["uri"]
		result["nextCursor"] = base64.b64encode(f"{scope}\n{last}".encode()).decode("ascii")
	return result
