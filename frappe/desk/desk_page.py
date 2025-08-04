# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


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
def getpage(name: str):
	"""
	Load the page from `frappe.form` and send it via `frappe.response`
	"""

	doc = get(name)
	frappe.response.docs.append(doc)
