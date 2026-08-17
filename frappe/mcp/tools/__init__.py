# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The tool registry and the shared plumbing every tool call goes through."""

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe.mcp.protocol import METHOD_NOT_FOUND, McpError
from frappe.monitor import add_data_to_monitor
from frappe.utils import strip_html

SAVEPOINT = "mcp_tool_call"


@dataclass(frozen=True)
class Tool:
	name: str
	title: str
	description: str
	input_schema: dict[str, Any]
	handler: Callable[[dict[str, Any]], dict[str, Any]]
	annotations: dict[str, Any] = field(default_factory=dict)

	def definition(self) -> dict[str, Any]:
		return {
			"name": self.name,
			"title": self.title,
			"description": self.description,
			"inputSchema": self.input_schema,
			"annotations": self.annotations,
		}


@contextmanager
def form_dict(arguments: dict[str, Any]):
	"""Present the tool arguments as `frappe.form_dict` for the duration of a call.

	`make_form_dict` fills `form_dict` with the whole JSON-RPC envelope, but every
	whitelisted method and every API v2 handler reads its arguments from there.
	"""
	original = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict(arguments or {})
	try:
		yield frappe.local.form_dict
	finally:
		frappe.local.form_dict = original


def registry() -> list[Tool]:
	from frappe.mcp.tools import discover

	return sorted([discover.TOOL], key=lambda tool: tool.name)


def definitions() -> list[dict[str, Any]]:
	return [tool.definition() for tool in registry()]


def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
	tool = next((tool for tool in registry() if tool.name == name), None)
	if not tool:
		raise McpError(METHOD_NOT_FOUND, f"Unknown tool {name}", http_status_code=404)

	add_data_to_monitor(mcp_tool=name)

	frappe.db.savepoint(SAVEPOINT)
	try:
		with form_dict(arguments):
			structured = tool.handler(arguments)
	except McpError:
		frappe.db.rollback(save_point=SAVEPOINT)
		raise
	except Exception as e:
		# A failed call must not leave a partial write for `sync_database` to commit.
		frappe.db.rollback(save_point=SAVEPOINT)
		return error_result(e)

	return success_result(structured)


def success_result(structured: dict[str, Any]) -> dict[str, Any]:
	return {
		"content": [{"type": "text", "text": json.dumps(structured, indent=2, default=str)}],
		"structuredContent": structured,
		"isError": False,
	}


def error_result(exception: Exception) -> dict[str, Any]:
	"""Report a failed call as a readable result so that the model can self-correct."""
	return {
		"content": [{"type": "text", "text": _error_message(exception)}],
		"isError": True,
	}


def _error_message(exception: Exception) -> str:
	"""The exception message, without markup and without a traceback."""
	message = str(exception).strip()
	if not message:
		message = " ".join(entry.get("message", "") for entry in frappe.local.message_log)

	frappe.clear_messages()

	message = strip_html(message).strip()
	return message or type(exception).__name__
