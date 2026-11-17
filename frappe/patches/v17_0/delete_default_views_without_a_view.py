# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.doctype_view.app_views import app_views


def execute():
	"""Delete the Default View rows that name a saved view no layer has any more: a deleted site view used to leave them."""
	pointers = frappe.get_all(
		"Default View", filters={"view": ("!=", "")}, fields=["name", "reference_doctype", "view"]
	)
	saved = set(frappe.get_all("Doctype View", fields=["reference_doctype", "key"], as_list=True))

	dangling = [
		pointer.name
		for pointer in pointers
		if (pointer.reference_doctype, pointer.view) not in saved
		and pointer.view not in app_views(pointer.reference_doctype)
	]
	for name in dangling:
		frappe.delete_doc("Default View", name, ignore_permissions=True, delete_permanently=True)
