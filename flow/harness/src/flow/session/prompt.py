"""Sectioned system-prompt composition: default preamble, global and project AGENTS.md
files, client suffix. `SessionStore.create` runs this once and stores the resolved
prompt on the config, so a session's prompt never changes after create."""

from __future__ import annotations

import os

from flow.session.config import SessionConfig

DEFAULT_PREAMBLE = """\
You are a coding agent. You work inside the user's project directory with real tools.

Rules:
- Be direct and concise. Lead with the answer; explain only when it adds value.
- Read the relevant code before you change it. Do not guess file contents or APIs.
- Prefer small, focused changes. Match the style of the surrounding code.
- Use the tools for every interaction with the system; never invent tool output.
- After a change, verify it: run the tests or the code path the change affects.
- Stop and ask before an action that is destructive or hard to reverse.
- If you are blocked or the task is ambiguous, say so plainly instead of guessing.
- Report results honestly, including failures and partial results."""


def build_system_prompt(config: SessionConfig, home: str | None = None) -> str:
	"""Resolve the session's system prompt. A verbatim `system_prompt` wins outright;
	otherwise compose preamble -> $HOME/AGENTS.md -> project AGENTS.md chain -> suffix."""
	if config.system_prompt is not None:
		return config.system_prompt
	home = os.path.realpath(home if home is not None else os.path.expanduser("~"))
	sections: list[str] = []
	preamble = config.system_preamble if config.system_preamble is not None else DEFAULT_PREAMBLE
	sections.append(preamble)
	global_path = os.path.join(home, "AGENTS.md")
	text = _read(global_path)
	if text is not None:
		sections.append(f"# Global instructions ({global_path})\n\n{text}")
	for directory in _project_dirs(config.cwd, home):
		path = os.path.join(directory, "AGENTS.md")
		text = _read(path)
		if text is not None:
			sections.append(f"# Project instructions ({path})\n\n{text}")
	if config.system_suffix is not None:
		sections.append(config.system_suffix)
	return "\n\n".join(section.strip() for section in sections if section.strip())


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
