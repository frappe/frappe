from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype("Error Log")

	from frappe.core.doctype.error_log.error_log import set_old_logs_as_seen
	set_old_logs_as_seen()
