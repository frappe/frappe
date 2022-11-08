# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe


@frappe.whitelist()
def get(name):
	"""
	Return the :term:`doclist` of the `Page` specified by `name`
	"""
	page = frappe.get_doc("Page", name)
	if page.is_permitted():
		page.load_assets()
		docs = frappe._dict(page.as_dict())
		if getattr(page, "_dynamic_page", None):
			docs["_dynamic_page"] = 1

		return docs
	else:
		frappe.response["403"] = 1
		raise frappe.PermissionError("No read permission for Page %s" % (page.title or name))


@frappe.whitelist(allow_guest=True)
def getpage():
	"""
	Load the page from `frappe.form` and send it via `frappe.response`
	"""
	page = frappe.form_dict.get("name")
	doc = get(page)

	frappe.response.docs.append(doc)


def has_permission(page):
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return True

	page_roles = [d.role for d in page.get("roles")]
	if page_roles:
		if frappe.session.user == "Guest" and "Guest" not in page_roles:
			return False
		elif not set(page_roles).intersection(set(frappe.get_roles())):
			# check if roles match
			return False

	if not frappe.has_permission("Page", ptype="read", doc=page):
		# check if there are any user_permissions
		return False
	else:
		# hack for home pages! if no Has Roles, allow everyone to see!
		return True
