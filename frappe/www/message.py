# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import strip_html_tags
from frappe.utils.html_utils import clean_html

no_cache = 1


def get_context(context):
	message_context = frappe._dict()
	if hasattr(frappe.local, "message"):
		message_context["header"] = frappe.local.message_title
		message_context["title"] = strip_html_tags(frappe.local.message_title)
		message_context["message"] = frappe.local.message
		if hasattr(frappe.local, "message_success"):
			message_context["success"] = frappe.local.message_success

	elif frappe.local.form_dict.id:
		message_id = frappe.local.form_dict.id
		key = f"message_id:{message_id}"
		message = frappe.cache().get_value(key, expires=True)
		if message:
			message_context.update(message.get("context", {}))
			if message.get("http_status_code"):
				frappe.local.response["http_status_code"] = message["http_status_code"]

	if not message_context.title:
		message_context.title = clean_html(frappe.form_dict.title)

	if not message_context.message:
		message_context.message = clean_html(frappe.form_dict.message)

	return message_context
