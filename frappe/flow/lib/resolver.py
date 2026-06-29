# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.utils.safe_exec import safe_exec

from flow.lib.tool import Tool, build_schema

if TYPE_CHECKING:
	from flow.flow.doctype.flow_tool.flow_tool import FlowTool

MAIN_FUNCTION_NAME = "main"
RESULT_VAR = "ai_tool_result"
ARG_VAR_PREFIX = "ai_tool_arg_"

_PRIMITIVE_BY_NAME: dict[str, dict[str, str]] = {
	"str": {"type": "string"},
	"int": {"type": "integer"},
	"float": {"type": "number"},
	"bool": {"type": "boolean"},
	"bytes": {"type": "string"},
}
_ARRAY_NAMES = frozenset(
	{"list", "List", "set", "Set", "frozenset", "FrozenSet", "tuple", "Tuple", "Sequence", "Iterable"}
)
_OBJECT_NAMES = frozenset({"dict", "Dict", "Mapping"})


def resolve_tool(doc: FlowTool, *, restrict_commit_rollback: bool = False) -> Tool:
	"""Turn a Flow Tool row into a runtime Tool the Agent can call.

	`restrict_commit_rollback` removes commit/rollback from a Script tool's sandbox,
	so it cannot escape a surrounding test transaction.
	"""
	if doc.type == "Imported":
		return _resolve_module(doc)
	return _resolve_script(doc, restrict_commit_rollback=restrict_commit_rollback)


def _resolve_module(doc: FlowTool) -> Tool:
	try:
		obj = frappe.get_attr(doc.import_path)
	except Exception as e:
		frappe.throw(
			_("Could not import tool from {0}: {1}").format(doc.import_path, e),
			title=_("Tool Import Failed"),
		)

	if isinstance(obj, Tool):
		return _build_tool(doc, obj.parameters, obj.func, confirm_prompt=obj.confirm_prompt)
	if callable(obj):
		return _build_tool(doc, build_schema(obj), obj)
	frappe.throw(
		_("Import path {0} is not a Tool or callable.").format(doc.import_path),
		title=_("Invalid Tool"),
	)


def _resolve_script(doc: FlowTool, *, restrict_commit_rollback: bool = False) -> Tool:
	runner = _make_script_runner(doc.code, doc.slug, restrict_commit_rollback=restrict_commit_rollback)
	return _build_tool(doc, schema_from_code(doc.code), runner)


def _build_tool(doc: FlowTool, parameters: dict[str, Any], func: Any, *, confirm_prompt: Any = None) -> Tool:
	return Tool(
		name=doc.slug,
		description=doc.description,
		parameters=parameters,
		func=func,
		requires_confirmation=bool(doc.requires_confirmation),
		confirm_prompt=confirm_prompt,
	)


def _make_script_runner(code: str, slug: str, *, restrict_commit_rollback: bool = False):
	"""Build a callable that runs a Script tool's `main` in the server-script sandbox."""

	def run(**kwargs: Any) -> Any:
		injected: dict[str, Any] = {}
		call_parts: list[str] = []
		for i, (name, value) in enumerate(kwargs.items()):
			var = f"{ARG_VAR_PREFIX}{i}"
			injected[var] = value
			call_parts.append(f"{name}={var}")

		script = f"{code}\n{RESULT_VAR} = {MAIN_FUNCTION_NAME}({', '.join(call_parts)})\n"
		exec_globals, _locals = safe_exec(
			script, injected, script_filename=slug, restrict_commit_rollback=restrict_commit_rollback
		)
		return exec_globals.get(RESULT_VAR)

	return run


def schema_from_code(code: str) -> dict[str, Any]:
	"""Derive a JSON Schema for a Script tool's arguments from `main`'s signature.

	Reads type annotations from the AST without evaluating them, so untrusted code
	cannot run during schema derivation.
	"""
	main = _find_main(ast.parse(code))
	params = main.args.posonlyargs + main.args.args + main.args.kwonlyargs
	required = _required_arg_names(main.args)

	properties = {param.arg: _annotation_schema(param.annotation) for param in params}
	schema: dict[str, Any] = {
		"type": "object",
		"properties": properties,
		"additionalProperties": False,
	}
	ordered_required = [param.arg for param in params if param.arg in required]
	if ordered_required:
		schema["required"] = ordered_required
	return schema


def _find_main(tree: ast.Module) -> ast.FunctionDef:
	for node in tree.body:
		if isinstance(node, ast.FunctionDef) and node.name == MAIN_FUNCTION_NAME:
			return node
	frappe.throw(_("Code must define a top-level <code>main</code> function."), title=_("Missing main()"))


def _required_arg_names(args: ast.arguments) -> set[str]:
	required: set[str] = set()
	positional = args.posonlyargs + args.args
	num_required = len(positional) - len(args.defaults)
	for i, arg in enumerate(positional):
		if i < num_required:
			required.add(arg.arg)
	for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
		if default is None:
			required.add(arg.arg)
	return required


def _annotation_schema(node: ast.expr | None) -> dict[str, Any]:
	if node is None:
		return {}
	if isinstance(node, ast.Name):
		return _schema_by_name(node.id)
	if isinstance(node, ast.Attribute):
		return _schema_by_name(node.attr)
	if isinstance(node, ast.Constant):
		return _schema_by_name(node.value) if isinstance(node.value, str) else {}
	if isinstance(node, ast.Subscript):
		return _subscript_schema(node)
	if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
		return _union_schema([node.left, node.right])
	return {}


def _schema_by_name(name: str) -> dict[str, Any]:
	if name in _PRIMITIVE_BY_NAME:
		return dict(_PRIMITIVE_BY_NAME[name])
	if name in _ARRAY_NAMES:
		return {"type": "array"}
	if name in _OBJECT_NAMES:
		return {"type": "object"}
	return {}


def _subscript_schema(node: ast.Subscript) -> dict[str, Any]:
	base = node.value
	base_name = (
		base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
	)
	sliced = node.slice

	if base_name == "Literal":
		return _literal_schema(sliced)
	if base_name == "Annotated":
		return _annotated_schema(sliced)
	if base_name == "Optional":
		return _annotation_schema(sliced)
	if base_name == "Union":
		elts = sliced.elts if isinstance(sliced, ast.Tuple) else [sliced]
		return _union_schema(elts)
	if base_name in _ARRAY_NAMES:
		element = sliced.elts[0] if isinstance(sliced, ast.Tuple) else sliced
		items = _annotation_schema(element)
		return {"type": "array", "items": items} if items else {"type": "array"}
	if base_name in _OBJECT_NAMES:
		return {"type": "object"}
	return {}


def _union_schema(nodes: list[ast.expr]) -> dict[str, Any]:
	schemas = [_annotation_schema(n) for n in nodes if not _is_none(n)]
	if not schemas:
		return {}
	if len(schemas) == 1:
		return schemas[0]
	return {"anyOf": schemas}


def _is_none(node: ast.expr) -> bool:
	if isinstance(node, ast.Constant):
		return node.value is None
	return isinstance(node, ast.Name) and node.id == "None"


def _literal_schema(sliced: ast.expr) -> dict[str, Any]:
	elts = sliced.elts if isinstance(sliced, ast.Tuple) else [sliced]
	values = [e.value for e in elts if isinstance(e, ast.Constant)]
	if not values:
		return {}

	schema: dict[str, Any] = {"enum": values}
	value_types = {type(v) for v in values}
	if value_types == {str}:
		schema["type"] = "string"
	elif value_types == {bool}:
		schema["type"] = "boolean"
	elif value_types <= {int}:
		schema["type"] = "integer"
	elif value_types <= {int, float}:
		schema["type"] = "number"
	return schema


def _annotated_schema(sliced: ast.expr) -> dict[str, Any]:
	if not isinstance(sliced, ast.Tuple) or not sliced.elts:
		return {}
	schema = _annotation_schema(sliced.elts[0])
	for meta in sliced.elts[1:]:
		if isinstance(meta, ast.Constant) and isinstance(meta.value, str):
			return {**schema, "description": meta.value}
	return schema
