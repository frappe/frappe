# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import strip_html_tags

no_cache = 1


def get_context(context):
	message_context = {}
	if hasattr(frappe.local, "message"):
		message_context["header"] = frappe.local.message_title
		message_context["title"] = strip_html_tags(frappe.local.message_title)
		message_context["message"] = frappe.local.message
		if hasattr(frappe.local, "message_success"):
			message_context["success"] = frappe.local.message_success

	elif frappe.local.form_dict.id:
		message_id = frappe.local.form_dict.id
		key = "message_id:{0}".format(message_id)
		message = frappe.cache().get_value(key, expires=True)
		if message:
			message_context.update(message.get("context", {}))
			if message.get("http_status_code"):
				frappe.local.response["http_status_code"] = message["http_status_code"]

	return message_context
