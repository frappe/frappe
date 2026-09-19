# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from frappe import _
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

no_cache = 1


def get_context(context):
	import frappe
	from frappe.core.doctype.user.passkey import link_allows_passkey

	context.no_breadcrumbs = True
	context.parents = [{"name": "me", "title": _("My Account")}]
	context.logo = get_app_logo()
	# Passkey enrollment is offered only on links requested from an authenticated desk
	# session. A forget-password link can set a password, not a passkey.
	context.allow_passkey = link_allows_passkey(frappe.form_dict.get("key"))
