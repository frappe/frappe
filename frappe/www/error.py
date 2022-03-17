# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe

no_cache = 1

def get_context(context):
	if frappe.flags.in_migrate: return
	context.http_status_code = 500

	print(frappe.get_traceback())
	return {"error": frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;") }
