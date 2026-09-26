# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.utils import slug
from frappe.permissions import check_doctype_permission


def get(name):
	"""
	Return the :term:`doclist` of the `Page` specified by `name`
	"""
	try:
		page = frappe.get_doc("Page", name)
	except frappe.DoesNotExistError:
		matches = frappe.get_all(
			"DocType", {"name": ("like", name.replace("-", "_")), "istable": 0}, pluck="name"
		)
		if doctype := next((d for d in matches if slug(d) == name), None):
			check_doctype_permission(doctype)
		raise

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
