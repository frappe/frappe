# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The MCP endpoint built into each site."""

from werkzeug.exceptions import NotFound
from werkzeug.routing import Rule

import frappe


def handle():
	if frappe.conf.get("disable_mcp_server"):
		raise NotFound

	from frappe.mcp.transport import handle_request

	return handle_request(frappe.request)


url_rules = [Rule("/mcp", methods=["POST", "GET", "DELETE"], endpoint=handle)]
