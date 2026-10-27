"""Tool hook payloads for extensions, modeled on pi/tau's `tool_call`/`tool_result` hooks.

A handler receives one event and returns the matching result, or None to pass.
`tool_call` handlers can block a call or rewrite its arguments before it runs;
`tool_result` handlers can rewrite what the model sees after it ran. Handlers
may be sync or async. `tool_call` fires before the confirm gate, so approval
prompts show the effective arguments; a resumed approval re-checks blocking only.
A gated call is therefore checked twice, so keep handlers side-effect free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flow_harness.events import ToolResult

HOOK_EVENTS = ("tool_call", "tool_result")


@dataclass(frozen=True, slots=True)
class PreToolUseEvent:
	"""Fires before a tool executes (ahead of any approval gate)."""

	tool_name: str
	arguments: Mapping[str, Any]
	cwd: str


@dataclass(frozen=True, slots=True)
class PreToolUseDecision:
	"""`block=True` prevents execution (`reason` goes back to the model); `arguments`
	rewrites the call. Blocking wins over rewrites and short-circuits remaining handlers."""

	block: bool = False
	reason: str | None = None
	arguments: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PostToolUseEvent:
	"""Fires after a tool executed; `arguments` are the effective (possibly rewritten) ones."""

	tool_name: str
	arguments: Mapping[str, Any]
	result: ToolResult


@dataclass(frozen=True, slots=True)
class PostToolUseOverride:
	"""Set `content` and/or `details` to override the tool's result; None keeps it.

	`details` replaces the whole dict (so a hook can also remove keys) — to add a
	key, spread the old ones: ``details={**event.result.details, "extra": ...}``."""

	content: str | None = None
	details: dict | None = None
