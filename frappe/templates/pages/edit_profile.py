# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

no_cache = 1
no_sitemap = 1

def get_context(context):
	user = frappe.get_doc('User', frappe.session.user)
	user.full_name = user.get_fullname()
	context.user = user
	context.show_sidebar=True

@frappe.whitelist()
def update_user(fullname, phone=None):
	if not fullname:
		return _("Name is required")

	user = frappe.get_doc('User', frappe.session.user)
	user.first_name = fullname
	user.last_name = ''
	user.phone = phone
	user.save(ignore_permissions=True)

	frappe.local.cookie_manager.set_cookie("full_name", fullname)

	return _("Updated")
