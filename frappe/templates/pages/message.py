# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import strip_html_tags

no_cache = 1
no_sitemap = 1

def get_context(context):
	message_context = {}
	if hasattr(frappe.local, "message"):
		message_context["header"] = frappe.local.message_title
		message_context["title"] = strip_html_tags(frappe.local.message_title)
		message_context["message"] = frappe.local.message
		if hasattr(frappe.local, "message_success"):
			message_context["success"] = frappe.local.message_success

	return message_context
