# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.user import get_fullname_and_avatar
import frappe.templates.pages.list

no_cache = 1
no_sitemap = 1

def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page."), frappe.PermissionError)

	context.my_account_list = frappe.get_all('Portal Menu Item',
		fields=['title', 'route', 'reference_doctype'], filters={'enabled': 1}, order_by='idx asc')

	for item in context.my_account_list:
		if item.reference_doctype:
			item.count = len(frappe.templates.pages.list.get(item.reference_doctype).get('result'))

	info = get_fullname_and_avatar(frappe.session.user)
	context["fullname"] = info.fullname
	context["user_image"] = info.avatar
