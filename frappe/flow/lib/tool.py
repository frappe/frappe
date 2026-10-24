# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, validate_call

_PRIMITIVE_SCHEMAS: dict[type, dict[str, str]] = {
	str: {"type": "string"},
	int: {"type": "integer"},
	float: {"type": "number"},
	bool: {"type": "boolean"},
	bytes: {"type": "string"},
}
_SKIP = {"ctx", "self", "cls"}


@dataclass(kw_only=True)
class ToolContext:
	"""Trusted context Flow injects into an imported tool, never exposed to the model."""

	session_id: str
	agent: str
	user: str


@dataclass
class Tool:
	name: str
	description: str
	parameters: dict[str, Any]
	func: Callable[..., Any]
	requires_confirmation: bool = False
	confirm_prompt: Callable[[dict[str, Any]], str] | None = None
	background: bool | Callable[[dict[str, Any]], bool] = False
	display_template: str | None = None

	def __post_init__(self) -> None:
		if "ctx" not in inspect.signature(self.func).parameters:
			raise TypeError(f"Tool {self.name} must take `*, ctx: ToolContext`.")
		if self.display_template:
			from flow_harness.tools.tool import display_template_variables  # loads every harness tool

			unknown = set(display_template_variables(self.display_template)) - set(
				self.parameters.get("properties", {})
			)
			if unknown:
				names = ", ".join(sorted(unknown))
				raise ValueError(f"Tool {self.name}'s display template names unknown argument(s): {names}.")
		self._validated = validate_call(config=ConfigDict(arbitrary_types_allowed=True))(self.func)

	def __call__(self, **kwargs: Any) -> Any:
		return self._validated(**kwargs)

	def to_dict(self) -> dict[str, Any]:
		schema: dict[str, Any] = {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description,
				"parameters": self.parameters,
			},
		}
		if self.display_template:
			schema["display_template"] = self.display_template
		return schema


def tool(
	func: Callable[..., Any] | None = None,
	*,
	name: str | None = None,
	description: str | None = None,
	requires_confirmation: bool = False,
	confirm_prompt: Callable[[dict[str, Any]], str] | None = None,
	background: bool | Callable[[dict[str, Any]], bool] = False,
	display_template: str | None = None,
) -> Tool | Callable[[Callable[..., Any]], Tool]:
	def wrap(f: Callable[..., Any]) -> Tool:
		if not callable(f):
			raise TypeError("@tool can only be applied to callables")
		return Tool(
			name=name or f.__name__,
			description=description or (inspect.getdoc(f) or "").strip(),
			parameters=build_schema(f),
			func=f,
			requires_confirmation=requires_confirmation,
			confirm_prompt=confirm_prompt,
			background=background,
			display_template=display_template,
		)

	return wrap(func) if func is not None else wrap


def build_schema(func: Callable[..., Any]) -> dict[str, Any]:
	sig = inspect.signature(func)
	hints = get_type_hints(func, include_extras=True)

	properties: dict[str, dict[str, Any]] = {}
	required: list[str] = []

	for param_name, param in sig.parameters.items():
		if param_name in _SKIP or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
			continue

		hint = hints.get(param_name, Any)
		actual_type, description = _unwrap_annotated(hint)
		actual_type, is_optional = _unwrap_optional(actual_type)

		prop_schema = _type_to_schema(actual_type)
		if description:
			prop_schema["description"] = description

		properties[param_name] = prop_schema
		if param.default is inspect.Parameter.empty and not is_optional:
			required.append(param_name)

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
	origin = get_origin(t)
	if origin not in (Union, types.UnionType):
		return t, False

	args = get_args(t)
	if type(None) not in args:
		return t, False

	remaining = tuple(a for a in args if a is not type(None))
	if len(remaining) == 1:
		return remaining[0], True
	if not remaining:
		return Any, True
	return Union[remaining], True  # noqa: UP007


def _type_to_schema(t: Any) -> dict[str, Any]:
	if t is Any or t is object or t is None:
		return {}

	if t in _PRIMITIVE_SCHEMAS:
		return dict(_PRIMITIVE_SCHEMAS[t])

	if t is dict:
		return {"type": "object"}
	if t is list:
		return {"type": "array"}

	origin = get_origin(t)
	args = get_args(t)

	if origin in (list, tuple, set, frozenset):
		items_schema = _type_to_schema(args[0]) if args else {}
		return {"type": "array", "items": items_schema}

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
