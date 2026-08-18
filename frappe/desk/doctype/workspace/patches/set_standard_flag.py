# Backfill the `standard` flag on app-shipped workspaces.
#
# The `standard` field was introduced on the revamp-workspaces branch to mark
# app-owned workspaces. Existing workspaces that already carry a `module` and
# `app` were shipped by an app, so flag them as standard. Private (non-public)
# workspaces are user-owned and must never be treated as standard.

import frappe


def execute():
	for workspace in frappe.get_all(
		"Workspace",
		filters={"public": 1},
		fields=["name", "module", "app", "standard"],
	):
		if workspace.module and workspace.app and not workspace.standard:
			frappe.db.set_value("Workspace", workspace.name, "standard", 1, update_modified=False)
