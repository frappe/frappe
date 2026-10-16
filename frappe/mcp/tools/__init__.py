# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Shared validation and execution for the built-in tools."""

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from pydantic.json_schema import GenerateJsonSchema

import frappe
from frappe.mcp.protocol import INVALID_PARAMS, METHOD_NOT_FOUND, McpError
from frappe.monitor import add_data_to_monitor
from frappe.utils import strip_html
from frappe.utils.response import json_handler


class CompactJsonSchema(GenerateJsonSchema):
	"""Leave out schema keywords that cost model context without adding meaning."""

	def generate(self, schema, mode="validation"):
		json_schema = super().generate(schema, mode)
		json_schema.pop("title", None)
		return json_schema

	def field_title_should_be_set(self, schema) -> bool:
		return False

	def nullable_schema(self, schema):
		return self.generate_inner(schema["schema"])

	def default_schema(self, schema):
		json_schema = super().default_schema(schema)
		if json_schema.get("default", ...) is None:
			del json_schema["default"]
		return json_schema

	def list_schema(self, schema):
		json_schema = super().list_schema(schema)
		if json_schema.get("items") == {}:
			del json_schema["items"]
		return json_schema

	def dict_schema(self, schema):
		json_schema = super().dict_schema(schema)
		if json_schema.get("additionalProperties") is True:
			del json_schema["additionalProperties"]
		return json_schema


class ToolArguments(BaseModel):
	"""Reject coercion and unknown arguments at the tool boundary."""

	model_config = ConfigDict(strict=True, extra="forbid")


# Autoincrement names are listed as integers. Handlers get strings, as REST URLs give them.
DocumentName = Annotated[Annotated[str, Field(min_length=1)] | int, AfterValidator(str)]


@dataclass(frozen=True)
class Tool:
	name: str
	arguments: type[ToolArguments]
	handler: Callable[..., Any]
	description: str | None = None
	annotations: dict[str, Any] = field(default_factory=dict)

	@cached_property
	def input_schema(self) -> dict:
		return self.arguments.model_json_schema(schema_generator=CompactJsonSchema)

	def definition(self) -> dict:
		definition = {"name": self.name, "inputSchema": self.input_schema, "annotations": self.annotations}
		if self.description:
			definition["description"] = self.description
		return definition


def registry() -> tuple[Tool, ...]:
	from frappe.mcp.tools.discover import (
		GET_DOCTYPE_SCHEMA,
		GET_METHOD_SCHEMA,
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
		SEARCH_DOCTYPES,
		GET_DOCTYPE_SCHEMA,
		SEARCH_METHODS,
		GET_METHOD_SCHEMA,
		LIST_DOCUMENT_METHODS,
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
		raise McpError(INVALID_PARAMS, "Tool name must be a string")
	tool = next((tool for tool in registry() if tool.name == name), None)
	if tool is None:
		raise McpError(METHOD_NOT_FOUND, "Unknown MCP tool: {0}".format(name), status=404)

	add_data_to_monitor(mcp_tool=name)
	try:
		arguments = tool.arguments.model_validate(params.get("arguments", {}))
	except ValidationError as error:
		return error_result(validation_message(error))

	with form_dict(arguments.model_dump()):
		return success_result(tool.handler(**frappe.form_dict))


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


def success_result(value: Any) -> dict:
	structured = value if isinstance(value, dict) else {"result": value}
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
	return "Invalid tool arguments: {0}".format("; ".join(issues))


def error_result(message: str) -> dict:
	frappe.clear_messages()
	return {"content": [{"type": "text", "text": strip_html(message).strip()}], "isError": True}
