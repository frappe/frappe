"""Keep tool arguments and failed writes inside one Frappe operation."""

import json
from contextlib import contextmanager

from mcp.server.mcpserver.exceptions import ToolError

import frappe
from frappe import _
from frappe.monitor import add_data_to_monitor
from frappe.utils import strip_html


@contextmanager
def tool_call(name, arguments=None, http_method=None):
	form_dict, response = frappe.local.form_dict, frappe.local.response
	method = frappe.request.method
	frappe.db.savepoint("mcp_tool")
	try:
		frappe.local.form_dict = frappe._dict(arguments or {})
		frappe.local.response = frappe._dict(docs=[])
		if http_method:
			frappe.request.method = http_method
		add_data_to_monitor(mcp_tool=name)
		yield
	except Exception as error:
		# SDK tool errors are HTTP successes, so Frappe would otherwise commit partial writes.
		frappe.db.rollback(save_point="mcp_tool")
		if isinstance(error, frappe.ValidationError | frappe.PermissionError | frappe.DoesNotExistError):
			message = str(error) or " ".join(entry.get("message", "") for entry in frappe.local.message_log)
			message = strip_html(message).strip() or _("The tool call failed")
			frappe.clear_messages()
			raise ToolError(message) from error
		raise
	finally:
		frappe.local.form_dict, frappe.local.response = form_dict, response
		frappe.request.method = method


def result(data):
	# Convert dates, decimals, and Documents before leaving the tool savepoint.
	return json.loads(frappe.as_json(data))
