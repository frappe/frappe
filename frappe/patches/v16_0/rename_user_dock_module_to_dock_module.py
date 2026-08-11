# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	"""`User Dock Module` is now `Dock Module`, shared by the site's dock layer and each user's.

	Runs before the model sync so the site's existing table is carried over to the new name
	rather than the new doctype being created empty alongside it -- the same placement, for the
	same reason, as `rename_workspace_customization_to_custom_workspace`.

	The doctype has never been released, so no upgrading site has rows under the old name. What
	it does have is sites that already ran `migrate_user_workspaces_to_dock_modules`, which
	wrote every user's dock curation into it; that patch is marked done and will not run again,
	so without this the curation it migrated would be stranded in the old table.
	"""
	if not frappe.db.table_exists("User Dock Module"):
		return

	if frappe.db.table_exists("Dock Module"):
		# already renamed (or a re-run after a partial migrate) -- nothing to carry over
		return

	rename_doc("DocType", "User Dock Module", "Dock Module", force=True)
	frappe.reload_doc("core", "doctype", "dock_module")
