# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo
from frappe.utils.password import is_password_login_disabled

no_cache = 1


def get_context(context):
	if is_password_login_disabled(frappe.session.user):
		frappe.throw(_("Password login is disabled, so you cannot set a password."), frappe.PermissionError)

	context.no_breadcrumbs = True
	context.parents = [{"name": "me", "title": _("My Account")}]
	context.logo = get_app_logo()
