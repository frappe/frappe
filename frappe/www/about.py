# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.doctypes import AboutUsSettings

sitemap = 1


def get_context(context):
	context.doc = AboutUsSettings.docs.get(cached=True)
	if context.doc.is_disabled:
		frappe.local.flags.redirect_location = "/404"
		raise frappe.Redirect
	return context
