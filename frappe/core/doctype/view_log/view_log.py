# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class ViewLog(Document):
	pass


def make_view_log(doctype, docname, user=None, unique_views=False):
	if not user:
		user = frappe.session.user

	if unique_views and frappe.db.exists(
		"View Log", {"reference_doctype": doctype, "reference_name": docname, "viewed_by": user}
	):
		return

	frappe.get_doc(
		{
			"doctype": "View Log",
			"viewed_by": user,
			"reference_doctype": doctype,
			"reference_name": docname,
		}
	).deferred_insert(ignore_permissions=True)
