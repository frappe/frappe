"""Built-in MCP endpoint using the official Python SDK."""

import anyio
from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Response

import frappe


def handle():
	if frappe.conf.disable_mcp_server:
		raise NotFound
	if frappe.session.user == "Guest":
		raise frappe.AuthenticationError
	if frappe.request.method != "POST":
		# The WSGI bridge buffers responses and cannot serve a long-lived SSE stream.
		return Response(status=405, headers={"Allow": "POST"})

	from frappe.mcp.transport import serve

	return anyio.run(serve, frappe.request)
