# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import frappe
from frappe.ai.resolver import resolve_tool

if TYPE_CHECKING:
	from frappe.ai.doctype.ai_tool.ai_tool import AITool
	from frappe.ai.tool import Tool

ERROR_LIMIT = 2000


@dataclass
class ToolTestResult:
	ok: bool
	result: Any = None
	error: str | None = None


def test_tool(doc: AITool, args: dict[str, Any] | None = None) -> ToolTestResult:
	"""Resolve an AI Tool (possibly an unsaved draft) and run it without persisting.

	Script tools run with commit/rollback removed from their sandbox, so the run
	cannot escape the surrounding savepoint.
	"""
	tool = resolve_tool(doc, restrict_commit_rollback=True)
	return run_in_rollback(tool, args)


def run_in_rollback(tool: Tool, args: dict[str, Any] | None = None) -> ToolTestResult:
	"""Run a resolved tool inside a savepoint that is always rolled back."""
	save_point = f"ai_tool_test_{frappe.generate_hash(length=10)}"
	frappe.db.savepoint(save_point)
	try:
		result = tool(**(args or {}))
		return ToolTestResult(ok=True, result=result)
	except Exception as e:
		return ToolTestResult(ok=False, error=f"{type(e).__name__}: {e}"[:ERROR_LIMIT])
	finally:
		frappe.db.rollback(save_point=save_point)
