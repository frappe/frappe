"""The Tool abstraction, its runtime context, the @tool decorator, and the
OpenAI-style parameter-schema builder that derives a tool's schema from a
callable's signature.

`build_schema` is shared code: the daemon describes its own tools with it, and a
client (e.g. Flow) describes its client-side tools the same way. The injected
`ctx` parameter is runtime-only and never exposed to the model.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import operator
import re
import types
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints, overload

from pydantic import BaseModel, ConfigDict, validate_call

from flow_harness.events import AttachmentContent, DisplaySegment

_DISPLAY_VARIABLE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
DISPLAY_VALUE_CHARS = 512


def display_template_variables(template: str) -> tuple[str, ...]:
	"""Return the simple ``{{ argument }}`` variables used by a display template."""
	variables = tuple(dict.fromkeys(_DISPLAY_VARIABLE.findall(template)))
	remainder = _DISPLAY_VARIABLE.sub("", template)
	if "{{" in remainder or "}}" in remainder:
		raise ValueError("tool display supports only simple {{ argument }} placeholders")
	return variables


def render_tool_display(template: str, arguments: dict[str, Any]) -> list[DisplaySegment] | None:
	"""Render a display template into segments once every referenced argument is available."""
	variables = display_template_variables(template)
	if any(name not in arguments for name in variables):
		return None

	segments: list[DisplaySegment] = []
	position = 0
	for match in _DISPLAY_VARIABLE.finditer(template):
		if match.start() > position:
			segments.append(DisplaySegment(text=template[position : match.start()]))
		segments.append(DisplaySegment(text=_display_value(arguments[match.group(1)]), arg=match.group(1)))
		position = match.end()
	if position < len(template):
		segments.append(DisplaySegment(text=template[position:]))
	return segments


def _display_value(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, (dict, list)):
		return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:DISPLAY_VALUE_CHARS]
	return str(value)[:DISPLAY_VALUE_CHARS]


@dataclass(kw_only=True)
class ToolContext:
	"""Runtime state injected into a tool call by the loop; never seen by the model.
	Keyword-only, so a field can be added beside the ones it belongs with."""

	cwd: str = "."
	# Empty preserves the local-development default: unrestricted filesystem access.
	# When populated, every path-taking builtin must reject targets outside these roots.
	allowed_roots: tuple[str, ...] = ()
	# When enabled, dot-prefixed descendants of an allowed root are inaccessible.
	ignore_hidden_files: bool = False
	# Extra roots available only to read-only tools (for example global skills).
	read_only_roots: tuple[str, ...] = ()
	abort: asyncio.Event = field(default_factory=asyncio.Event)
	timeout: float = 120.0
	# stores image bytes beside the session log; None when the caller has no attachment store
	store_image: Callable[[str, bytes], Awaitable[AttachmentContent]] | None = None
	# runs a sub-agent: call id, task, agent name, id of a child to continue; None where none can run
	run_subagent: Callable[[str, str, str | None, str | None], Awaitable[SubagentOutcome]] | None = None
	# the call being executed, set per dispatch
	tool_call_id: str = ""


@dataclass
class ToolResult:
	"""A tool's outcome. `content` is the text the model sees; `details` is structured
	metadata for rich rendering/logging and is never sent to the model."""

	content: str
	details: dict[str, Any] = field(default_factory=dict)
	is_error: bool = False
	# images the tool produced; the loop copies these onto the durable event
	attachments: list[AttachmentContent] = field(default_factory=list)


@dataclass
class SubagentOutcome:
	"""What `ToolContext.run_subagent` reports back: how the child's run ended, and the
	agent it ran as."""

	agent: str
	end_reason: str
	text: str
	error: str | None = None


@dataclass
class Tool:
	name: str
	description: str
	parameters: dict[str, Any]
	func: Callable[..., Awaitable[ToolResult]]
	requires_confirmation: bool = False
	confirm_prompt: Callable[[dict[str, Any]], str] | None = None
	# System-prompt surface, separate from `description` (which goes into the tool
	# schema and carries the full usage rules). `prompt_snippet` is a one-line blurb
	# for the prompt's "Available tools" list; `prompt_guidelines` are bullets merged
	# (deduped) into the prompt's "Guidelines" section.
	prompt_snippet: str | None = None
	prompt_guidelines: tuple[str, ...] = ()
	# User-facing activity text. Simple ``{{ argument }}`` placeholders are filled
	# from streamed call arguments as soon as all referenced values are complete.
	display_template: str | None = None
	# May run alongside the other concurrent tools called in the same turn.
	concurrent: bool = False
	# A turn that calls only such tools, none failing, ends the run: no model turn follows.
	ends_run: bool = False

	def __post_init__(self) -> None:
		if self.display_template is not None:
			if not self.display_template.strip():
				raise ValueError("tool display template must not be empty")
			unknown = set(display_template_variables(self.display_template)) - set(
				self.parameters.get("properties", {})
			)
			if unknown:
				names = ", ".join(sorted(unknown))
				raise ValueError(f"tool display references unknown argument(s): {names}")
		self._validated = validate_call(config=ConfigDict(arbitrary_types_allowed=True))(self.func)

	def __call__(self, **kwargs: Any) -> Awaitable[ToolResult]:
		return self._validated(**kwargs)

	def to_schema(self) -> dict[str, Any]:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description,
				"parameters": self.parameters,
			},
		}


@overload
def tool(func: Callable[..., Awaitable[ToolResult]], /) -> Tool: ...


@overload
def tool(
	*,
	name: str | None = None,
	description: str | None = None,
	requires_confirmation: bool = False,
	confirm_prompt: Callable[[dict[str, Any]], str] | None = None,
	prompt_snippet: str | None = None,
	prompt_guidelines: tuple[str, ...] = (),
	display_template: str | None = None,
	concurrent: bool = False,
	ends_run: bool = False,
) -> Callable[[Callable[..., Awaitable[ToolResult]]], Tool]: ...


def tool(
	func: Callable[..., Awaitable[ToolResult]] | None = None,
	*,
	name: str | None = None,
	description: str | None = None,
	requires_confirmation: bool = False,
	confirm_prompt: Callable[[dict[str, Any]], str] | None = None,
	prompt_snippet: str | None = None,
	prompt_guidelines: tuple[str, ...] = (),
	display_template: str | None = None,
	concurrent: bool = False,
	ends_run: bool = False,
) -> Tool | Callable[[Callable[..., Awaitable[ToolResult]]], Tool]:
	def wrap(f: Callable[..., Awaitable[ToolResult]]) -> Tool:
		return Tool(
			name=name or getattr(f, "__name__", f.__class__.__name__),
			description=description or (inspect.getdoc(f) or "").strip(),
			parameters=build_schema(f),
			func=f,
			requires_confirmation=requires_confirmation,
			confirm_prompt=confirm_prompt,
			prompt_snippet=prompt_snippet,
			prompt_guidelines=prompt_guidelines,
			display_template=display_template,
			concurrent=concurrent,
			ends_run=ends_run,
		)

	return wrap(func) if func is not None else wrap


# --- parameter schema builder ---------------------------------------------

_PRIMITIVES: dict[type, dict[str, str]] = {
	str: {"type": "string"},
	int: {"type": "integer"},
	float: {"type": "number"},
	bool: {"type": "boolean"},
	bytes: {"type": "string"},
}

_SKIP = {"ctx", "self", "cls"}


def build_schema(func: Callable[..., Any]) -> dict[str, Any]:
	sig = inspect.signature(func)
	try:
		hints = get_type_hints(func, include_extras=True)
	except Exception:
		hints = {}

	properties: dict[str, dict[str, Any]] = {}
	required: list[str] = []
	for name, param in sig.parameters.items():
		if name in _SKIP or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
			continue
		actual, description = _unwrap_annotated(hints.get(name, Any))
		actual, is_optional = _unwrap_optional(actual)
		prop = _type_to_schema(actual)
		if description:
			prop["description"] = description
		properties[name] = prop
		if param.default is inspect.Parameter.empty and not is_optional:
			required.append(name)

	schema: dict[str, Any] = {
		"type": "object",
		"properties": properties,
		"additionalProperties": False,
	}
	if required:
		schema["required"] = required
	return schema


def _unwrap_annotated(t: Any) -> tuple[Any, str | None]:
	metadata = getattr(t, "__metadata__", None)
	if metadata is None:
		return t, None
	actual = getattr(t, "__origin__", t)
	description = next((m for m in metadata if isinstance(m, str)), None)
	return actual, description


def _unwrap_optional(t: Any) -> tuple[Any, bool]:
	if get_origin(t) not in (Union, types.UnionType):
		return t, False
	args = get_args(t)
	if type(None) not in args:
		return t, False
	remaining = tuple(a for a in args if a is not type(None))
	if len(remaining) == 1:
		return remaining[0], True
	if not remaining:
		return Any, True
	return functools.reduce(operator.or_, remaining), True


def _type_to_schema(t: Any) -> dict[str, Any]:
	if t is Any or t is object or t is None:
		return {}
	if t in _PRIMITIVES:
		return dict(_PRIMITIVES[t])
	if t is dict:
		return {"type": "object"}
	if t is list:
		return {"type": "array"}

	origin = get_origin(t)
	args = get_args(t)
	if origin in (list, tuple, set, frozenset):
		return {"type": "array", "items": _type_to_schema(args[0]) if args else {}}
	if origin is dict:
		return {"type": "object"}
	if origin is Literal:
		return _enum_schema(list(args))
	if origin in (Union, types.UnionType):
		return {"anyOf": [_type_to_schema(a) for a in args]}

	if isinstance(t, type):
		if issubclass(t, BaseModel):
			return _inline_pydantic_refs(t.model_json_schema())
		if issubclass(t, Enum):
			return _enum_schema([m.value for m in t])
	return {}


def _inline_pydantic_refs(schema: dict[str, Any]) -> dict[str, Any]:
	defs = schema.pop("$defs", {})
	if not defs:
		return schema

	resolved: dict[str, dict[str, Any]] = {}

	def walk(node: Any) -> Any:
		if isinstance(node, list):
			return [walk(item) for item in node]
		if not isinstance(node, dict):
			return node
		ref = node.get("$ref")
		if isinstance(ref, str) and ref.startswith("#/$defs/"):
			def_name = ref.split("/")[-1]
			if def_name in resolved:
				return resolved[def_name]
			if def_name in defs:
				return walk(defs[def_name])
			return {"type": "object"}
		return {key: walk(value) for key, value in node.items()}

	for def_name, def_schema in defs.items():
		resolved[def_name] = walk(def_schema)
	return walk(schema)


def _enum_schema(values: list[Any]) -> dict[str, Any]:
	value_types = {type(v) for v in values}
	if value_types == {str}:
		return {"type": "string", "enum": values}
	if value_types == {bool}:
		return {"type": "boolean", "enum": values}
	if value_types <= {int}:
		return {"type": "integer", "enum": values}
	if value_types <= {int, float}:
		return {"type": "number", "enum": values}
	return {"enum": values}
