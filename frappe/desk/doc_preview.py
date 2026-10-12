# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.form.load import set_link_titles


@frappe.whitelist(methods=["GET"])
def get_preview(doctype: str, name: str):
	"""Doc for a read-only preview: read and field-level permissions applied, link titles set,
	no View Log written. The meta comes from the client's own cache."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	set_link_titles(doc)

	return {
		"doc": doc.as_dict(),
		"permlevels": doc.get_permlevel_access("read"),
	}
