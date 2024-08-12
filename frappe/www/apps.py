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

	system_default_app = frappe.get_system_settings("default_app")
	user_default_app = frappe.db.get_value("User", frappe.session.user, "default_app")
	default_app = user_default_app if user_default_app else system_default_app

	all_apps = get_apps()

	if len(all_apps) == 0:
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect

	for app in all_apps:
		app["is_default"] = True if app.get("name") == default_app else False

	return {"apps": all_apps}
