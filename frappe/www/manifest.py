# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo
from frappe.utils.data import get_url


def get_context(context):
	context.update(
		{
			"id": get_url(),
			"app_name": (
				frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or "Frappe"
			),
			"app_logo": get_app_logo(),
		}
	)

	return context
