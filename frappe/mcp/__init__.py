# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The MCP server built into every Frappe site.

An agent points its MCP client at `https://<site>/api/mcp` and gets a small tool
surface over the same semantics as the REST API v2. Authorization, CORS, rate
limiting and the `WWW-Authenticate` challenge all come from the normal request
pipeline, so this package only implements the protocol.

Set `disable_mcp_server` in `site_config.json` to turn the endpoint off.
"""

from werkzeug.routing import Rule
from werkzeug.wrappers import Response

import frappe


def handle() -> Response:
	if frappe.conf.get("disable_mcp_server"):
		raise frappe.DoesNotExistError

	from frappe.mcp import transport

	return transport.handle_request(frappe.local.request)


url_rules = [
	Rule("/mcp", methods=["POST", "GET", "DELETE"], endpoint=handle),
]
