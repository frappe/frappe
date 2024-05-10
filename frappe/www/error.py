# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.flags.in_migrate:
		return

	allow_traceback = frappe.get_system_settings("allow_error_traceback") if frappe.db else False

	context.error_title = context.error_title or _("Uncaught Server Exception")
	context.error_message = context.error_message or _("There was an error building this page")

	return {
		"error": frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;") if allow_traceback else ""
	}
