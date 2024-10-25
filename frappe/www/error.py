# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.flags.in_migrate:
		return

	allow_traceback = frappe.get_system_settings("allow_error_traceback") if frappe.db else False
	if frappe.local.flags.disable_traceback and not frappe.local.dev_server:
		allow_traceback = False

	if not context.title:
		context.title = _("Server Error")
	if not context.message:
		context.message = _("There was an error building this page")

	return {
		"error": frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;") if allow_traceback else ""
	}
