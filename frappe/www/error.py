# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import print_function, unicode_literals

import frappe

no_cache = 1


def get_context(context):
	if frappe.flags.in_migrate:
		return
	context.http_status_code = 500
	print(frappe.get_traceback())
	return {"error": frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;")}
