# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Shared validation and execution for the built-in tools."""

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

import frappe
from frappe import _
from frappe.mcp.protocol import INVALID_PARAMS, METHOD_NOT_FOUND, McpError
from frappe.monitor import add_data_to_monitor
from frappe.utils import strip_html
from frappe.utils.response import json_handler


class ToolArguments(BaseModel):
	"""Reject coercion and unknown arguments at the tool boundary."""

	model_config = ConfigDict(strict=True, extra="forbid")


@dataclass(frozen=True)
class Tool:
	name: str
	description: str
	arguments: type[ToolArguments]
	handler: Callable[..., Any]
	annotations: dict[str, Any] = field(default_factory=dict)

	@cached_property
	def input_schema(self) -> dict:
		return self.arguments.model_json_schema()

	def definition(self) -> dict:
		return {
			"name": self.name,
			"description": _("Site: {0}. {1}").format(frappe.local.site, _(self.description)),
			"inputSchema": self.input_schema,
			"annotations": self.annotations,
		}


def registry() -> tuple[Tool, ...]:
	from frappe.mcp.tools.discover import (
		GET_DOCTYPE_SCHEMA,
		GET_DOCUMENT_METHOD_SCHEMA,
		GET_METHOD_SCHEMA,
		GET_SITE_INFO,
		LIST_DOCUMENT_METHODS,
		SEARCH_DOCTYPES,
		SEARCH_METHODS,
	)
	from frappe.mcp.tools.documents import (
		COUNT_DOCUMENTS,
		CREATE_DOCUMENT,
		DELETE_DOCUMENT,
		GET_DOCUMENT,
		LIST_DOCUMENTS,
		UPDATE_DOCUMENT,
	)
	from frappe.mcp.tools.methods import CALL_DOCUMENT_METHOD, CALL_METHOD

	return (
		GET_SITE_INFO,
		SEARCH_DOCTYPES,
		GET_DOCTYPE_SCHEMA,
		SEARCH_METHODS,
		GET_METHOD_SCHEMA,
		LIST_DOCUMENT_METHODS,
		GET_DOCUMENT_METHOD_SCHEMA,
		LIST_DOCUMENTS,
		GET_DOCUMENT,
		COUNT_DOCUMENTS,
		CREATE_DOCUMENT,
		UPDATE_DOCUMENT,
		DELETE_DOCUMENT,
		CALL_METHOD,
		CALL_DOCUMENT_METHOD,
	)


def definitions() -> list[dict]:
	return [tool.definition() for tool in registry()]


def call(params: dict) -> dict:
	name = params.get("name")
	if not isinstance(name, str):
		raise McpError(INVALID_PARAMS, _("Tool name must be a string"))
	tool = next((tool for tool in registry() if tool.name == name), None)
	if tool is None:
		raise McpError(METHOD_NOT_FOUND, _("Unknown MCP tool: {0}").format(name), status=404)

	add_data_to_monitor(mcp_tool=name)
	identity = {"site": frappe.local.site, "user": frappe.session.user}
	try:
		arguments = tool.arguments.model_validate(params.get("arguments", {}))
	except ValidationError as error:
		return error_result(validation_message(error), identity)

	try:
		with form_dict(arguments.model_dump()):
			result = success_result(tool.handler(**frappe.form_dict), identity)
	except Exception as error:
		# Tool errors are returned as results; roll back before the POST request can commit.
		frappe.db.rollback()
		result = error_result(str(error) or type(error).__name__, identity)
	return result


@contextmanager
def form_dict(arguments: dict) -> Iterator[dict]:
	"""Keep REST handlers' argument and response state inside the tool call."""
	original_arguments = frappe.local.form_dict
	original_response = frappe.local.response
	frappe.local.form_dict = frappe._dict(arguments)
	frappe.local.response = frappe._dict({"docs": []})
	try:
		yield frappe.local.form_dict
	finally:
		frappe.local.form_dict = original_arguments
		frappe.local.response = original_response


def success_result(value: Any, identity: dict[str, str]) -> dict:
	structured = value if isinstance(value, dict) else {"result": value}
	structured = {**structured, **identity}
	# Normalize dates and other Frappe values before the request commits.
	text = json.dumps(structured, default=json_handler, allow_nan=False)
	return {
		"content": [{"type": "text", "text": text}],
		"structuredContent": json.loads(text),
		"isError": False,
	}


def validation_message(error: ValidationError) -> str:
	issues = []
	for issue in error.errors(include_input=False, include_url=False, include_context=False):
		location = ".".join(str(part) for part in issue["loc"]) or "arguments"
		issues.append(f"{location}: {issue['msg']}")
	return _("Invalid tool arguments: {0}").format("; ".join(issues))


def error_result(message: str, identity: dict[str, str]) -> dict:
	frappe.clear_messages()
	message = strip_html(message).strip()
	return {
		"content": [{"type": "text", "text": message}, {"type": "text", "text": json.dumps(identity)}],
		"structuredContent": {**identity, "error": message},
		"isError": True,
	}
