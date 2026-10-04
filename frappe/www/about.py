# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

settings = frappe.get_doc("About Us Settings")
if not settings.is_disabled:
	sitemap = 1


def get_context(context):
	context.doc = frappe.get_cached_doc("About Us Settings")
	if context.doc.is_disabled:
		frappe.local.flags.redirect_location = "/404"
		raise frappe.Redirect
	return context
