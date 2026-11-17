# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The MCP endpoint built into each site."""

from werkzeug.exceptions import NotFound

import frappe


def handle():
	if not frappe.get_system_settings("enable_mcp"):
		raise NotFound

	from frappe.mcp.transport import handle_request

	return handle_request(frappe.request)
