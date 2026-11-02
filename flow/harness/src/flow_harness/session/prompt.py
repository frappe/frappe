"""System-prompt composition, modeled on pi's: a short static intro, an "Available
tools" list of one-line snippets, a deduped "Guidelines" section contributed by the
active tools, AGENTS.md files wrapped in a <project_context> block, and a trailing
"Current working directory" line. The full tool-usage rules stay in each tool's
schema description; the prompt only carries the one-liners.

`SessionStore.create` runs this once and stores the resolved prompt on the config,
so a session's prompt never changes after create.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from flow_harness.path_policy import canonical_path
from flow_harness.session.config import SessionConfig
from flow_harness.session.skills import Skill, format_skills_for_prompt
from flow_harness.tools import Tool, select_tools

DEFAULT_INTRO = (
	"You are an expert coding assistant operating inside flow, a coding agent harness. "
	"You help users by reading files, executing commands, editing code, and writing new files."
)

CUSTOM_TOOLS_NOTE = (
	"In addition to the tools above, you may have access to other custom tools depending on the project."
)

TAIL_GUIDELINES = (
	"Be concise in your responses",
	"Show file paths clearly when working with files",
)

_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# a wheel carries flow's docs and examples under the package; a checkout keeps them at the harness root
_DOC_ROOTS = (os.path.join(_PACKAGE_ROOT, "data"), os.path.dirname(os.path.dirname(_PACKAGE_ROOT)))


def build_system_prompt(
	config: SessionConfig,
	home: str | None = None,
	*,
	skills: Sequence[Skill] = (),
	tools: Sequence[Tool] | None = None,
) -> str:
	"""Resolve the session's system prompt. A verbatim `system_prompt` wins outright;
	otherwise compose body -> suffix -> <project_context> -> cwd trailer. `system_append`
	lands last either way."""
	if config.system_prompt is not None:
		return _appended(config.system_prompt, config.system_append)
	home = os.path.realpath(home if home is not None else os.path.expanduser("~"))
	sections: list[str] = []
	body = config.system_preamble if config.system_preamble is not None else _default_body(config, tools)
	sections.append(body)
	if config.system_suffix is not None:
		sections.append(config.system_suffix)
	context = _project_context(config, home)
	if context is not None:
		sections.append(context)
	if "read" in config.tools:
		skill_index = format_skills_for_prompt(skills)
		if skill_index:
			sections.append(skill_index)
	sections.append(f"Current working directory: {config.cwd.replace(os.sep, '/')}")
	if config.system_append is not None:
		sections.append(config.system_append)
	return "\n\n".join(section.strip() for section in sections if section.strip())


def _appended(prompt: str, append: str | None) -> str:
	if not append or not append.strip():
		return prompt
	return f"{prompt.strip()}\n\n{append.strip()}" if prompt.strip() else append.strip()


def _default_body(config: SessionConfig, tools: Sequence[Tool] | None = None) -> str:
	active_tools = list(tools) if tools is not None else list(select_tools(config.tools).values())
	snippets = [f"- {tool.name}: {tool.prompt_snippet}" for tool in active_tools if tool.prompt_snippet]
	guidelines: list[str] = []
	for t in active_tools:
		for guideline in t.prompt_guidelines:
			if guideline not in guidelines:
				guidelines.append(guideline)
	guidelines.extend(g for g in TAIL_GUIDELINES if g not in guidelines)
	parts = [
		DEFAULT_INTRO,
		"Available tools:\n" + ("\n".join(snippets) or "(none)"),
		CUSTOM_TOOLS_NOTE,
		"Guidelines:\n" + "\n".join(f"- {g}" for g in guidelines),
	]
	docs = _docs_section(active_tools)
	if docs is not None:
		parts.append(docs)
	return "\n\n".join(parts)


def _docs_section(active_tools: Sequence[Tool]) -> str | None:
	"""Point the model at flow's own docs, pi-style, so a question about flow is answered
	from them and a customization is written as an extension rather than a source edit."""
	docs = _docs_dir("docs")
	if docs is None or not any(tool.name in ("read", "bash") for tool in active_tools):
		return None
	lines = [
		"Flow documentation (read only for questions related to flow itself or extentions):",
		f"- Docs: {docs}",
	]
	examples = _docs_dir("examples")
	if examples is not None:
		lines.append(f"- Examples: {examples}")
	lines.extend(
		[
			"- Resolve docs/... and examples/... under those roots, not the cwd",
			"- extensions.md, skills.md, tools.md (tools and client hooks), api.md, architecture.md",
			"- Customize flow with an extension, never by editing its source; read "
			"docs/extensions.md fully, links included, before starting",
		]
	)
	return "\n".join(lines)


def doc_roots() -> tuple[str, ...]:
	"""Flow's docs and examples directories, for a fenced session to read but not write."""
	found = (_docs_dir("docs"), _docs_dir("examples"))
	return tuple(canonical_path(path) for path in found if path is not None)


def _docs_dir(name: str) -> str | None:
	"""Flow's own `name` directory, as installed or as checked out; None when it ships neither."""
	for root in _DOC_ROOTS:
		path = os.path.join(root, name)
		if os.path.isdir(path):
			return path
	return None


def strip_tool_from_prompt(prompt: str, name: str) -> str:
	"""The prompt without the tools-list line of `name`, for a child that lacks the tool."""
	return "\n".join(line for line in prompt.split("\n") if not line.startswith(f"- {name}: "))


def _project_context(config: SessionConfig, home: str) -> str | None:
	"""AGENTS.md files wrapped pi-style: $HOME/AGENTS.md first, then the project
	chain outermost first."""
	entries: list[tuple[str, str]] = []
	global_path = os.path.join(home, "AGENTS.md")
	text = _read(global_path)
	if text is not None:
		entries.append((global_path, text))
	for directory in _project_dirs(config.cwd, home):
		path = os.path.join(directory, "AGENTS.md")
		text = _read(path)
		if text is not None:
			entries.append((path, text))
	if not entries:
		return None
	blocks = "\n\n".join(
		f'<project_instructions path="{path}">\n{text}\n</project_instructions>' for path, text in entries
	)
	return f"<project_context>\n\nProject-specific instructions and guidelines:\n\n{blocks}\n\n</project_context>"


def _project_dirs(cwd: str, home: str) -> list[str]:
	"""Ancestor directories of `cwd` that may hold a project AGENTS.md, outermost first.
	The walk stops at the git root (included; `.git` may be a file in a worktree) or at
	`home` (excluded — home/AGENTS.md is the global section), whichever comes first."""
	dirs: list[str] = []
	current = os.path.realpath(cwd)
	while current != home:
		dirs.append(current)
		if os.path.exists(os.path.join(current, ".git")):
			break
		parent = os.path.dirname(current)
		if parent == current:
			break
		current = parent
	dirs.reverse()
	return dirs


def _read(path: str) -> str | None:
	try:
		with open(path, encoding="utf-8") as f:
			text = f.read().strip()
	except OSError:
		return None
	return text or None
