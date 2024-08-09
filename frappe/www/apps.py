# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _
from frappe.apps import get_apps


def get_context():
	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

	if frappe.session.data.user_type == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	return {"apps": get_apps()}
