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


def _assigns_result(tree: ast.Module) -> bool:
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign):
			targets = node.targets
		elif isinstance(node, ast.AugAssign | ast.AnnAssign | ast.NamedExpr):
			targets = [node.target]
		else:
			continue
		for target in targets:
			if isinstance(target, ast.Name) and target.id == RESULT_VAR:
				return True
			if isinstance(target, ast.Tuple | ast.List) and any(
				isinstance(el, ast.Name) and el.id == RESULT_VAR for el in target.elts
			):
				return True
	return False
