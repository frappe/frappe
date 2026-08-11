# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	"""`Workspace Customization` is now `Custom Workspace` -- rename it, keeping every row.

	Runs before the model sync so the site's existing table is carried over to the new name
	rather than the new doctype being created empty alongside it.
	"""
	if not frappe.db.table_exists("Workspace Customization"):
		return

	if frappe.db.table_exists("Custom Workspace"):
		# already renamed (or a re-run after a partial migrate) -- nothing to carry over
		return

	rename_doc("DocType", "Workspace Customization", "Custom Workspace", force=True)
	frappe.reload_doc("desk", "doctype", "custom_workspace")
