# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""User-authored conditions, run in the server-script sandbox (safe_exec).

A condition is either a single Python expression whose value is the verdict,
or a multi-line script that sets a `result` variable. Authoring is restricted
to System Managers (Flow Trigger / Flow Knowledge Source permissions), the
same trust level frappe requires for Server Scripts.
"""

from __future__ import annotations

import ast
from typing import Any

import frappe
from frappe import _
from frappe.utils.safe_exec import safe_exec

RESULT_VAR = "result"


def validate_condition(condition: str | None) -> None:
	"""Save-time check: a single expression, or a script that sets `result`."""
	if not condition:
		return
	if _is_expression(condition):
		return
	try:
		tree = ast.parse(condition)
	except SyntaxError as e:
		frappe.throw(_("Invalid condition: {0}").format(e), title=_("Invalid Condition"))
	if not _assigns_result(tree):
		frappe.throw(
			_("A multi-line condition must set a <code>result</code> variable."),
			title=_("Invalid Condition"),
		)


def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
	"""Run `condition` in the sandbox with `context` in scope; return the verdict.
	Raises on execution errors — callers decide how to fail."""
	script = f"{RESULT_VAR} = ({condition}\n)" if _is_expression(condition) else condition
	exec_globals, _locals = safe_exec(script, context, script_filename="flow_condition")
	return bool(exec_globals.get(RESULT_VAR))


def _is_expression(condition: str) -> bool:
	try:
		compile(condition, "<flow_condition>", "eval")
		return True
	except SyntaxError:
		return False


# Scopes that don't execute in the module body, so a `result` assigned inside them
# never reaches the exec globals the verdict is read from.
_NESTED_SCOPES = (
	ast.FunctionDef,
	ast.AsyncFunctionDef,
	ast.ClassDef,
	ast.Lambda,
	ast.ListComp,
	ast.SetComp,
	ast.DictComp,
	ast.GeneratorExp,
)


def _assigns_result(node: ast.AST) -> bool:
	"""Whether `result` is assigned in the module's own scope. Recurses through control
	flow (if/for/try) but not into nested scopes, which never run in the exec globals."""
	for child in ast.iter_child_nodes(node):
		if isinstance(child, _NESTED_SCOPES):
			continue
		if _targets_result(child) or _assigns_result(child):
			return True
	return False


def _targets_result(node: ast.AST) -> bool:
	if isinstance(node, ast.Assign):
		targets = node.targets
	elif isinstance(node, ast.AugAssign | ast.AnnAssign | ast.NamedExpr):
		targets = [node.target]
	else:
		return False
	return any(_is_result_name(target) for target in targets)


def _is_result_name(target: ast.AST) -> bool:
	if isinstance(target, ast.Name):
		return target.id == RESULT_VAR
	if isinstance(target, ast.Tuple | ast.List):
		return any(_is_result_name(el) for el in target.elts)
	return False
