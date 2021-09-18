# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

sitemap = 1

def get_context(context):
	context.doc = frappe.get_doc("About Us Settings", "About Us Settings")

	return context
