# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

no_cache = 1
no_sitemap = 1

def get_context(context):
	print frappe.get_traceback()
	return {"error": frappe.get_traceback() }
