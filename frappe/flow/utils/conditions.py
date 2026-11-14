# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""User-authored conditions: a single Python expression run with `frappe.safe_eval`."""

from __future__ import annotations

import ast
from typing import Any

import frappe
from frappe import _


def validate_condition(condition: str | None) -> None:
	"""Save-time check: the condition must be a single expression."""
	if not condition:
		return
	try:
		ast.parse(condition, mode="eval")
	except SyntaxError as e:
		frappe.throw(
			_("Condition must be a single Python expression: {0}").format(str(e)),
			title=_("Invalid Condition"),
		)


def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
	"""Evaluate `condition` with only `context` (and `len`) in scope. Raises on errors."""
	return bool(frappe.safe_eval(condition, {**context, "len": len}))
