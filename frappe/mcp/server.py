"""Four SDK tools backed by Frappe API v2 operations."""

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

import frappe
from frappe import _
from frappe.api import v2
from frappe.mcp.context import result, tool_call
from frappe.mcp.discovery import discover_site
from frappe.mcp.methods import execute_method


def create_server():
	server = MCPServer(
		"frappe",
		version=frappe.__version__,
		instructions=_(
			"Use discover before choosing DocTypes, fields, or methods. "
			"Use get_documents for reads and write_documents for changes. "
			"Use call_method for whitelisted business logic, including submit and cancel. "
			"All calls use your Frappe permissions."
		),
		subscriptions=False,
	)
	server.add_tool(
		discover,
		structured_output=True,
		description=_(discover.__doc__),
		annotations=ToolAnnotations(read_only_hint=True),
	)
	server.add_tool(
		get_documents,
		structured_output=True,
		description=_(get_documents.__doc__),
		annotations=ToolAnnotations(read_only_hint=True),
	)
	server.add_tool(
		write_documents,
		structured_output=True,
		description=_(write_documents.__doc__),
		annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False),
	)
	server.add_tool(
		call_method,
		structured_output=True,
		description=_(call_method.__doc__),
		annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=False),
	)
	return server


async def discover(
	query: str | None = None, doctype: str | None = None, method: str | None = None
) -> dict[str, Any]:
	"""Discover the site, search names, inspect a DocType, or inspect a whitelisted method.

	Method discovery requires System Manager. DocType schemas require read permission.
	"""
	with tool_call("discover"):
		return result(discover_site(query, doctype, method))


async def get_documents(
	doctype: str,
	name: str | None = None,
	filters: dict[str, Any] | list | None = None,
	fields: list[str] | None = None,
	order_by: str | None = None,
	start: Annotated[int, Field(ge=0)] = 0,
	limit: Annotated[int, Field(ge=1, le=100)] = 20,
	count_only: bool = False,
) -> dict[str, Any]:
	"""Read one document by name, count matching documents, or list a bounded page."""
	arguments = {"filters": filters, "fields": fields, "start": start, "limit": limit}
	if order_by:
		arguments["order_by"] = order_by
	with tool_call("get_documents", arguments, "GET"):
		if name:
			return result({"document": v2.read_doc(doctype, name)})
		if count_only:
			return result({"doctype": doctype, "count": v2.count(doctype)})
		documents = v2.document_list(doctype)
		return result(
			{
				"doctype": doctype,
				"documents": documents,
				"start": start,
				"limit": limit,
				"has_next_page": bool(frappe.response.get("has_next_page")),
			}
		)


async def write_documents(
	action: Literal["create", "update", "delete"],
	doctype: str,
	name: str | None = None,
	data: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Create, update, or delete one document. Use call_method for submit and cancel."""
	with tool_call("write_documents", data, "POST"):
		if "flags" in frappe.form_dict or "doctype" in frappe.form_dict:
			frappe.throw(_("Document flags and doctype cannot be supplied in data"))
		if action == "create":
			return result({"action": action, "document": v2.create_doc(doctype)})
		if not name:
			frappe.throw(_("A document name is required"))
		if "name" in frappe.form_dict:
			frappe.throw(_("The document name cannot be changed in data"))
		if action == "update":
			return result({"action": action, "document": v2.update_doc(doctype, name)})
		v2.delete_doc(doctype, name)
		return {"action": action, "doctype": doctype, "name": name}


async def call_method(
	method: str,
	args: dict[str, Any] | None = None,
	doctype: str | None = None,
	name: str | None = None,
	http_method: Literal["GET", "POST", "PUT", "DELETE", "QUERY"] | None = None,
) -> dict[str, Any]:
	"""Call a dotted RPC method, a DocType module method, or a named document method.

	args contains method arguments. GET-only methods use GET. Other methods default to POST.
	http_method selects another allowed REST verb. Binary and multipart results are unsupported.
	"""
	with tool_call("call_method", args):
		return result(execute_method(method, doctype, name, http_method))
