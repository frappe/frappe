# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe

no_cache = 1
no_sitemap = 1

def get_context(context):
	message_context = {}
	if hasattr(frappe.local, "message"):
		message_context["title"] = frappe.local.message_title
		message_context["message"] = frappe.local.message
		if hasattr(frappe.local, "message_success"):
			message_context["success"] = frappe.local.message_success
	
	return message_context
