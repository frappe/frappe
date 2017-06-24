# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe

no_cache = 1
no_sitemap = 1

def get_context(context):
	if frappe.flags.in_migrate: return
	print(frappe.get_traceback().encode("utf-8"))
	return {"error": frappe.get_traceback().replace("<", "&lt;").replace(">", "&gt;") }
