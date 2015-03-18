# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.user import get_fullname_and_avatar

no_cache = 1
no_sitemap = 1

def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page."), frappe.PermissionError)

	context["my_account_list"] = []

	for element in frappe.get_hooks("my_account_context"):
		if isinstance(element, dict):
			context["my_account_list"].append(element)
		else:
			frappe.get_attr(element)(context)

	info = get_fullname_and_avatar(frappe.session.user)
	context["fullname"] = info.fullname
	context["user_image"] = info.avatar
