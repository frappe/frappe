"""Discovery and expansion of harness-neutral Agent Skills resources."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from html import escape

import yaml
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.path_policy import canonical_path, is_path_allowed

MAX_SKILL_BYTES = 256 * 1024
MAX_SKILL_FRONTMATTER_BYTES = 16 * 1024
MAX_SKILL_INVOCATION_BYTES = 256 * 1024
MAX_SKILL_INDEX_BYTES = 64 * 1024
MAX_SKILL_CANDIDATES = 500
MAX_SKILL_DIRECTORY_ENTRIES = 2000
MAX_SKILLS = 200
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_FRONTMATTER_BYTES_RE = re.compile(rb"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv"}
# a "/skill:<name>" word anywhere in a message
_SKILL_TOKEN_RE = re.compile(r"(?<!\S)/skill:(\S+)")
_SKILL_BLOCK_RE = re.compile(r'<skill name="([^"]+)" location="([^"]+)">\n([\s\S]*?)\n</skill>(?:\n\n|\Z)')


class SkillError(ValueError):
	"""A skill resource or explicit invocation is invalid."""


class Skill(BaseModel):
	"""Validated metadata retained in a session's skill catalog."""

	model_config = ConfigDict(extra="forbid", frozen=True)

	name: str
	description: str
	path: str
	canonical_path: str
	disable_model_invocation: bool = False

	@property
	def base_dir(self) -> str:
		return os.path.dirname(self.canonical_path)


class SkillDiagnostic(BaseModel):
	model_config = ConfigDict(extra="forbid", frozen=True)

	path: str
	message: str


class SkillCatalog(BaseModel):
	model_config = ConfigDict(extra="forbid", frozen=True)

	skills: tuple[Skill, ...] = Field(default_factory=tuple)
	diagnostics: tuple[SkillDiagnostic, ...] = Field(default_factory=tuple)


@dataclass(frozen=True)
class SkillInvocation:
	"""The skills a message uses and the message text."""

	skills: tuple[InvokedSkill, ...]
	instructions: str | None


@dataclass(frozen=True)
class InvokedSkill:
	"""A skill a message uses, with the body read from its file."""

	skill: Skill
	content: str


@dataclass(frozen=True)
class ParsedSkillInvocation:
	"""Presentation fields recovered from Flow's expanded message format."""

	skills: tuple[ParsedSkill, ...]
	instructions: str | None

	@property
	def command(self) -> str:
		"""The message as the user typed it."""
		name = self.skills[0].name
		if self.instructions and name in _skill_commands(self.instructions):
			return self.instructions
		return f"/skill:{name} {self.instructions}" if self.instructions else f"/skill:{name}"


@dataclass(frozen=True)
class ParsedSkill:
	"""One `<skill>` block of an expanded message."""

	name: str
	location: str
	content: str


def global_skills_root() -> str:
	return os.path.join(os.path.realpath(os.path.expanduser("~")), ".agents", "skills")


def list_skill_files(root: str) -> tuple[tuple[str, ...], bool]:
	"""Every `<name>/SKILL.md` directly under `root`, valid or not, and whether the
	scan stopped at the entry cap."""
	return _skill_files(root, include_root_skill=False)


def discover_skills(
	cwd: str,
	*,
	home: str | None = None,
	enabled: bool = True,
	extra_paths: Sequence[str] = (),
	allowed_roots: Sequence[str] = (),
) -> SkillCatalog:
	"""Discover skills in precedence order, with project and later roots winning."""
	if not enabled and not extra_paths:
		return SkillCatalog()

	resolved_home = os.path.realpath(home if home is not None else os.path.expanduser("~"))
	roots: list[tuple[str, bool, bool]] = []
	if enabled:
		roots.extend(
			[
				(os.path.join(resolved_home, ".agents", "skills"), True, False),
				(os.path.join(os.path.realpath(cwd), ".agents", "skills"), False, False),
			]
		)
	for raw in extra_paths:
		expanded = os.path.expanduser(raw.strip())
		roots.append(
			(
				os.path.abspath(expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)),
				False,
				True,
			)
		)

	# Scan higher-precedence roots first. This makes the skill quota deterministic
	# without allowing a full global catalog to crowd out project overrides.
	by_name: dict[str, Skill] = {}
	seen_paths: set[str] = set()
	diagnostics: list[SkillDiagnostic] = []
	candidate_count = 0
	catalog_limit_reported = False
	candidate_limit_reported = False

	for root, is_global, include_root_skill in reversed(roots):
		policy_roots = (canonical_path(root), *allowed_roots) if is_global else allowed_roots
		paths, directory_truncated = _skill_files(root, include_root_skill=include_root_skill)
		if directory_truncated:
			diagnostics.append(
				SkillDiagnostic(
					path=root,
					message=(f"skill directory entry limit of {MAX_SKILL_DIRECTORY_ENTRIES} reached"),
				)
			)
		for path in paths:
			if candidate_count >= MAX_SKILL_CANDIDATES:
				if not candidate_limit_reported:
					diagnostics.append(
						SkillDiagnostic(
							path=root,
							message=f"skill candidate limit of {MAX_SKILL_CANDIDATES} reached",
						)
					)
					candidate_limit_reported = True
				break
			candidate_count += 1
			canonical = canonical_path(path)
			# Global skill files are a read-only exception to the project fence, but
			# child symlinks may not escape the declared global root unless their target
			# is otherwise allowed. An empty policy remains unrestricted for local use.
			if allowed_roots and not is_path_allowed(canonical, policy_roots):
				diagnostics.append(SkillDiagnostic(path=path, message="skill is outside allowed roots"))
				continue
			if canonical in seen_paths:
				continue
			try:
				skill = load_skill(path, expected_path=canonical)
			except SkillError as error:
				diagnostics.append(SkillDiagnostic(path=path, message=str(error)))
				continue
			seen_paths.add(canonical)

			winner = by_name.get(skill.name)
			if winner is not None:
				diagnostics.append(
					SkillDiagnostic(
						path=skill.path,
						message=f"skill {skill.name!r} is overridden by a higher-precedence source",
					)
				)
				continue
			if len(by_name) >= MAX_SKILLS:
				if not catalog_limit_reported:
					diagnostics.append(
						SkillDiagnostic(path=root, message=f"skill limit of {MAX_SKILLS} reached")
					)
					catalog_limit_reported = True
				continue
			by_name[skill.name] = skill
		if candidate_limit_reported:
			break

	return SkillCatalog(
		skills=sorted_skills(by_name.values()),
		diagnostics=tuple(diagnostics),
	)


def sorted_skills(skills: Iterable[Skill]) -> tuple[Skill, ...]:
	"""Catalog order: by name."""
	return tuple(sorted(skills, key=_skill_name))


def _skill_name(skill: Skill) -> str:
	return skill.name


def load_skill(path: str, *, expected_path: str | None = None) -> Skill:
	"""Read and validate one SKILL.md's bounded frontmatter."""
	canonical = expected_path or canonical_path(path)
	raw = _read_frontmatter(path, expected_path=canonical)
	metadata = _validate_metadata(raw, os.path.basename(os.path.dirname(os.path.abspath(path))))
	return Skill(
		name=metadata["name"],
		description=metadata["description"],
		path=os.path.abspath(path),
		canonical_path=canonical,
		disable_model_invocation=metadata.get("disable-model-invocation") is True,
	)


def validate_skill_text(text: str, parent_name: str) -> None:
	"""Reject SKILL.md content the loader would reject, before it is written."""
	match = _FRONTMATTER_RE.match(text)
	if match is not None and len(match.group(0).encode("utf-8")) > MAX_SKILL_FRONTMATTER_BYTES:
		raise SkillError(f"skill frontmatter exceeds {MAX_SKILL_FRONTMATTER_BYTES // 1024} KB")
	_validate_metadata(text, parent_name)


def _validate_metadata(raw: str, parent_name: str) -> dict:
	metadata, _ = _parse(raw)
	name = metadata.get("name")
	description = metadata.get("description")
	if not isinstance(name, str) or not valid_skill_name(name):
		raise SkillError("skill name must be 1-64 lowercase letters, digits, or single hyphens")
	if name != parent_name:
		raise SkillError(f"skill name {name!r} must match parent directory {parent_name!r}")
	if not isinstance(description, str) or not description.strip():
		raise SkillError("skill description is required")
	description = description.strip()
	if len(description) > 1024:
		raise SkillError("skill description exceeds 1024 characters")
	return {**metadata, "name": name, "description": description}


def valid_skill_name(name: str) -> bool:
	return bool(_NAME_RE.fullmatch(name)) and len(name) <= 64


def parse_skill_command(
	text: str,
	skills: Sequence[Skill],
	*,
	resolve: Callable[[str], Skill | None] | None = None,
) -> SkillInvocation | None:
	"""Expand each `/skill:name` in a message; None if it names no skill.

	`resolve` finds a skill added after the session was created."""
	stripped = text.strip()
	leading = stripped.startswith("/skill:")
	names: list[str] = []
	instructions = stripped
	if leading:
		parts = stripped.split(maxsplit=1)
		names.append(parts[0].removeprefix("/skill:"))
		if not names[0]:
			raise SkillError("skill command must include a name")
		instructions = parts[1].strip() if len(parts) > 1 else ""
	later = [name for name in _skill_commands(instructions) if valid_skill_name(name)]
	# named again later: keep the text as typed, leading command included
	if leading and names[0] in later:
		instructions = stripped
	names += later
	invoked: list[InvokedSkill] = []
	for index, name in enumerate(dict.fromkeys(names)):
		skill = next((item for item in skills if item.name == name), None)
		if skill is None and resolve is not None:
			skill = resolve(name)
		if skill is None:
			if leading and index == 0:
				raise SkillError(f"unknown skill: {name}")
			continue
		invoked.append(InvokedSkill(skill=skill, content=_skill_body(skill)))
	if not invoked:
		return None
	invocation = SkillInvocation(skills=tuple(invoked), instructions=instructions or None)
	if len(format_skill_invocation(invocation).encode("utf-8")) > MAX_SKILL_INVOCATION_BYTES:
		raise SkillError(f"expanded skill exceeds {MAX_SKILL_INVOCATION_BYTES // 1024} KB")
	return invocation


def _skill_commands(text: str) -> list[str]:
	"""Skill names in `text`, skipping quoted lines."""
	return [
		name
		for line in text.split("\n")
		if not line.startswith(">")
		for name in _SKILL_TOKEN_RE.findall(line)
	]


def _skill_body(skill: Skill) -> str:
	# Refuse a symlink swapped in since the skill was discovered, rather than reading
	# a different file under the same name.
	if canonical_path(skill.path) != skill.canonical_path:
		raise SkillError(f"skill path changed: {skill.name}")
	raw = _read_bounded(skill.path, expected_path=skill.canonical_path)
	_, body = _parse(raw)
	return body.strip()


def format_skill_invocation(invocation: SkillInvocation) -> str:
	"""Render an invocation as ordinary provider-facing user text, like Pi and Tau."""
	blocks = [
		f'<skill name="{escape(item.skill.name, quote=True)}" '
		f'location="{escape(item.skill.path, quote=True)}">\n'
		f"References are relative to {item.skill.base_dir}.\n\n"
		f"{item.content}\n"
		"</skill>"
		for item in invocation.skills
	]
	return "\n\n".join([*blocks, invocation.instructions] if invocation.instructions else blocks)


def parse_skill_invocation(text: str) -> ParsedSkillInvocation | None:
	"""Parse an expanded invocation for compact client display, as Pi and Tau do."""
	skills: list[ParsedSkill] = []
	end = 0
	while match := _SKILL_BLOCK_RE.match(text, end):
		skills.append(ParsedSkill(*match.groups()))
		end = match.end()
	if not skills:
		return None
	return ParsedSkillInvocation(skills=tuple(skills), instructions=text[end:] or None)


def format_skills_for_prompt(skills: Iterable[Skill]) -> str:
	visible = sorted((skill for skill in skills if not skill.disable_model_invocation), key=lambda s: s.name)
	if not visible:
		return ""
	lines = [
		"The following skills provide specialized instructions for specific tasks.",
		"Use read to load a skill's file when the task matches its description.",
		"Resolve relative paths in a skill against the directory containing its SKILL.md file.",
		"",
		"<available_skills>",
	]
	included = 0
	for skill in visible:
		block = [
			"  <skill>",
			f"    <name>{escape(skill.name)}</name>",
			f"    <description>{escape(skill.description)}</description>",
			f"    <location>{escape(skill.path)}</location>",
			"  </skill>",
		]
		candidate = "\n".join([*lines, *block, "</available_skills>"])
		if len(candidate.encode("utf-8")) > MAX_SKILL_INDEX_BYTES:
			continue
		lines.extend(block)
		included += 1
	if not included:
		return ""
	lines.append("</available_skills>")
	return "\n".join(lines)


def _skill_files(root: str, *, include_root_skill: bool) -> tuple[tuple[str, ...], bool]:
	"""Find a root skill or direct `<name>/SKILL.md` children, following symlinks."""
	if os.path.isfile(root):
		return ((root,) if os.path.basename(root) == "SKILL.md" else ()), False
	if not os.path.isdir(root):
		return (), False

	root_skill = os.path.join(root, "SKILL.md")
	if include_root_skill and os.path.isfile(root_skill):
		return (root_skill,), False

	entries: list[os.DirEntry[str]] = []
	truncated = False
	try:
		with os.scandir(root) as iterator:
			for entry in iterator:
				if len(entries) >= MAX_SKILL_DIRECTORY_ENTRIES:
					truncated = True
					break
				entries.append(entry)
	except OSError:
		return (), False

	paths: list[str] = []
	for entry in sorted(entries, key=lambda item: item.name):
		if entry.name.startswith(".") or entry.name in _SKIP_DIRS:
			continue
		try:
			is_directory = entry.is_dir(follow_symlinks=True)
		except OSError:
			continue
		if not is_directory:
			continue
		path = os.path.join(entry.path, "SKILL.md")
		if os.path.isfile(path):
			paths.append(path)
	return tuple(paths), truncated


def _read_frontmatter(path: str, *, expected_path: str) -> str:
	try:
		with open(path, "rb") as file:
			_verify_open_file(file, expected_path)
			if os.fstat(file.fileno()).st_size > MAX_SKILL_BYTES:
				raise SkillError(f"skill exceeds {MAX_SKILL_BYTES // 1024} KB")
			data = file.read(MAX_SKILL_FRONTMATTER_BYTES + 1)
	except SkillError:
		raise
	except OSError as error:
		raise SkillError(f"could not read skill: {error.strerror or type(error).__name__}") from None
	match = _FRONTMATTER_BYTES_RE.match(data)
	if match is None:
		if len(data) > MAX_SKILL_FRONTMATTER_BYTES:
			raise SkillError(f"skill frontmatter exceeds {MAX_SKILL_FRONTMATTER_BYTES // 1024} KB")
		frontmatter = data
	else:
		frontmatter = match.group(0)
	try:
		return frontmatter.decode("utf-8")
	except UnicodeDecodeError:
		raise SkillError("skill frontmatter must be UTF-8 text") from None


def _read_bounded(path: str, *, expected_path: str) -> str:
	try:
		with open(path, "rb") as file:
			_verify_open_file(file, expected_path)
			data = file.read(MAX_SKILL_BYTES + 1)
	except SkillError:
		raise
	except OSError as error:
		raise SkillError(f"could not read skill: {error.strerror or type(error).__name__}") from None
	if len(data) > MAX_SKILL_BYTES:
		raise SkillError(f"skill exceeds {MAX_SKILL_BYTES // 1024} KB")
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		raise SkillError("skill must be UTF-8 text") from None


def _verify_open_file(file, expected_path: str) -> None:
	"""Ensure a symlink still names the cataloged file after it has been opened."""
	opened = os.fstat(file.fileno())
	try:
		expected = os.stat(expected_path)
	except OSError as error:
		raise SkillError(f"could not read skill: {error.strerror or type(error).__name__}") from None
	if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
		raise SkillError("skill path changed during read")


def _parse(raw: str) -> tuple[dict, str]:
	match = _FRONTMATTER_RE.match(raw)
	if match is None:
		raise SkillError("skill requires YAML frontmatter")
	try:
		metadata = yaml.safe_load(match.group(1)) or {}
	except yaml.YAMLError:
		raise SkillError("invalid skill frontmatter") from None
	if not isinstance(metadata, dict):
		raise SkillError("skill frontmatter must be a mapping")
	return metadata, raw[match.end() :]
