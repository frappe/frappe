# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils.password import is_password_login_disabled
from frappe.utils.user import is_portal_user

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

	context.current_user = frappe.get_doc("User", frappe.session.user)
	context.show_sidebar = False
	context.is_portal_user = is_portal_user()
	context.password_login_disabled = is_password_login_disabled(frappe.session.user)
