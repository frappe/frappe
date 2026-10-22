"""The small runtime that owns loaded extensions, their registered tools, and tool hooks."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path

from flow_harness.events import ToolCall, ToolResult
from flow_harness.extensions.hooks import (
	HOOK_EVENTS,
	PostToolUseEvent,
	PostToolUseOverride,
	PreToolUseDecision,
	PreToolUseEvent,
)
from flow_harness.extensions.loader import ExtensionDiagnostic, LoadedExtension, load_extensions
from flow_harness.tools import Tool, ToolContext


@dataclass(frozen=True, slots=True)
class RegisteredExtension:
	name: str
	path: str


class ExtensionAPI:
	"""Object passed to an extension's ``setup(flow)`` entry point."""

	def __init__(self, runtime: ExtensionRuntime, extension_name: str) -> None:
		self._runtime = runtime
		self._extension_name = extension_name

	@property
	def name(self) -> str:
		return self._extension_name

	def register_tool(self, tool: Tool) -> None:
		"""Register a Flow ``Tool``. The first extension registration wins."""
		if not isinstance(tool, Tool):
			raise TypeError("register_tool expects a flow_harness.tools.Tool (usually created with @tool)")
		self._runtime.register_tool(self._extension_name, tool)

	def on(self, event: str, handler: Callable[..., object]) -> None:
		"""Subscribe to `tool_call` (block/rewrite a call) or `tool_result` (rewrite a result).

		The handler takes the event payload from `flow_harness.extensions.hooks` and returns the
		matching result dataclass, or None to pass. Sync or async."""
		if event not in HOOK_EVENTS:
			raise ValueError(f"unknown hook event {event!r} (expected one of: {', '.join(HOOK_EVENTS)})")
		if not callable(handler):
			raise TypeError(f"handler for `{event}` must be callable")
		self._runtime.register_handler(self._extension_name, event, handler)


class ExtensionRuntime:
	"""Loads extensions once and exposes their tools, hooks, and diagnostics."""

	def __init__(self) -> None:
		self._extensions: list[RegisteredExtension] = []
		self._tools: dict[str, Tool] = {}
		self._tool_sources: dict[str, str] = {}
		self._handlers: dict[str, list[tuple[str, Callable[..., object]]]] = {}
		self._diagnostics: list[ExtensionDiagnostic] = []
		self._seen_runtime_keys: set[tuple[str, str, str]] = set()

	def load(
		self,
		*,
		global_dir: Path | None,
		extra_paths: Sequence[Path] = (),
		include_global_dir: bool = True,
	) -> None:
		result = load_extensions(
			global_dir=global_dir,
			extra_paths=extra_paths,
			include_global_dir=include_global_dir,
		)
		self._diagnostics.extend(result.diagnostics)
		for extension in result.extensions:
			self._setup_extension(extension)

	def _setup_extension(self, extension: LoadedExtension) -> None:
		api = ExtensionAPI(self, extension.name)
		try:
			extension.setup(api)
		except Exception as error:  # extensions are an isolation boundary
			self._remove_registrations(extension.name)
			self._diagnostics.append(
				ExtensionDiagnostic(
					message=f"setup failed: {error!r}",
					path=str(extension.path),
					extension=extension.name,
					severity="error",
				)
			)
			return
		self._extensions.append(RegisteredExtension(extension.name, str(extension.path)))

	def register_tool(self, extension_name: str, tool: Tool) -> None:
		existing = self._tool_sources.get(tool.name)
		if existing is not None:
			self._diagnostics.append(
				ExtensionDiagnostic(
					message=(
						f"tool `{tool.name}` already registered by extension `{existing}`; ignoring duplicate"
					),
					extension=extension_name,
				)
			)
			return
		self._tools[tool.name] = tool
		self._tool_sources[tool.name] = extension_name

	def register_handler(self, extension_name: str, event: str, handler: Callable[..., object]) -> None:
		self._handlers.setdefault(event, []).append((extension_name, handler))

	def _remove_registrations(self, extension_name: str) -> None:
		for name, source in tuple(self._tool_sources.items()):
			if source == extension_name:
				self._tool_sources.pop(name, None)
				self._tools.pop(name, None)
		for event, handlers in self._handlers.items():
			self._handlers[event] = [entry for entry in handlers if entry[0] != extension_name]

	def compose_tools(
		self, builtin_tools: dict[str, Tool], extension_names: list[str] | None = None
	) -> dict[str, Tool]:
		"""Return selected built-ins plus extension tools — every one, or just
		`extension_names`; extensions override by name."""
		extension_tools = (
			self._tools
			if extension_names is None
			else {name: tool for name, tool in self._tools.items() if name in extension_names}
		)
		return {**builtin_tools, **extension_tools}

	# --- tool hook dispatch (semantics ported from pi/tau) --------------------

	@property
	def has_tool_hooks(self) -> bool:
		return any(self._handlers.values())

	async def run_tool_call_hooks(self, call: ToolCall, ctx: ToolContext) -> PreToolUseDecision:
		"""Run `tool_call` handlers in load order against one call about to execute.

		Each handler sees the current effective arguments. A raising handler blocks the
		call (fail-safe: a broken gate must not let the call through)."""
		arguments = dict(call.args)
		changed = False
		for extension_name, handler in self._handlers.get("tool_call", ()):
			event = PreToolUseEvent(tool_name=call.name, arguments=dict(arguments), cwd=ctx.cwd)
			try:
				result = await _resolve(handler(event))
			except Exception as error:
				self._record(extension_name, "tool_call", f"handler raised: {error!r}", "error")
				return PreToolUseDecision(
					block=True,
					reason=f"extension `{extension_name}` tool_call hook failed",
				)
			if result is None:
				continue
			if not isinstance(result, PreToolUseDecision):
				self._record(extension_name, "tool_call", _unsupported(result), "warning")
				continue
			if result.block:
				reason = result.reason if isinstance(result.reason, str) else None
				if result.reason is not None and reason is None:
					self._record(extension_name, "tool_call", _malformed("reason", result.reason), "warning")
				return PreToolUseDecision(
					block=True, reason=reason or f"Blocked by extension `{extension_name}`."
				)
			if result.arguments is not None:
				if not isinstance(result.arguments, Mapping):
					self._record(
						extension_name, "tool_call", _malformed("arguments", result.arguments), "warning"
					)
					continue
				arguments = dict(result.arguments)
				changed = True
		return PreToolUseDecision(arguments=arguments) if changed else PreToolUseDecision()

	async def run_tool_result_hooks(self, call: ToolCall, result: ToolResult) -> ToolResult:
		"""Run `tool_result` handlers in load order; each sees the previous rewrite.

		A raising handler is recorded and skipped — the result stands (fail-open)."""
		current = result
		for extension_name, handler in self._handlers.get("tool_result", ()):
			event = PostToolUseEvent(
				tool_name=call.name,
				arguments=dict(call.args),
				result=current.model_copy(update={"details": dict(current.details)}),
			)
			try:
				outcome = await _resolve(handler(event))
			except Exception as error:
				self._record(extension_name, "tool_result", f"handler raised: {error!r}", "error")
				continue
			if outcome is None:
				continue
			if not isinstance(outcome, PostToolUseOverride):
				self._record(extension_name, "tool_result", _unsupported(outcome), "warning")
				continue
			updates: dict = {}
			if outcome.content is not None:
				if isinstance(outcome.content, str):
					updates["content"] = outcome.content
				else:
					self._record(
						extension_name, "tool_result", _malformed("content", outcome.content), "warning"
					)
			if outcome.details is not None:
				if isinstance(outcome.details, Mapping):
					updates["details"] = dict(outcome.details)
				else:
					self._record(
						extension_name, "tool_result", _malformed("details", outcome.details), "warning"
					)
			if updates:
				current = current.model_copy(update=updates)
		return current

	def _record(self, extension_name: str, event: str, message: str, severity: str) -> None:
		# hooks run on every tool call, so an identical repeat is recorded once
		key = (extension_name, event, message)
		if key in self._seen_runtime_keys:
			return
		self._seen_runtime_keys.add(key)
		self._diagnostics.append(
			ExtensionDiagnostic(message=f"`{event}` {message}", extension=extension_name, severity=severity)
		)

	# --- inspection -----------------------------------------------------------

	@property
	def tools(self) -> dict[str, Tool]:
		return dict(self._tools)

	@property
	def tool_sources(self) -> dict[str, str]:
		return dict(self._tool_sources)

	@property
	def extensions(self) -> tuple[RegisteredExtension, ...]:
		return tuple(self._extensions)

	@property
	def diagnostics(self) -> tuple[ExtensionDiagnostic, ...]:
		return tuple(self._diagnostics)

	def info(self) -> dict:
		return {
			"extensions": [
				{
					"name": extension.name,
					"path": extension.path,
					"tools": [
						name for name, source in self._tool_sources.items() if source == extension.name
					],
					"hooks": [
						event
						for event in HOOK_EVENTS
						if any(name == extension.name for name, _ in self._handlers.get(event, ()))
					],
				}
				for extension in self._extensions
			],
			"diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
		}


def _unsupported(result: object) -> str:
	return f"handler returned unsupported result type {type(result).__name__}; ignored"


def _malformed(field: str, value: object) -> str:
	return f"handler returned `{field}` of unsupported type {type(value).__name__}; ignored"


async def _resolve(value: object) -> object:
	return await value if isawaitable(value) else value
