# Backfill the `standard` flag on app-shipped workspaces.
#
# The `standard` field marks a workspace an app owns: one that was imported from a JSON file
# in an app and is overwritten from that file on every migrate. It is also what
# `remove_orphan_entities` keys off, so flagging a site's own workspace standard would get it
# deleted -- the backfill has to be exact, not a heuristic.
#
# Having a file *is* the definition, so that is what this asks. It used to ask whether the
# workspace carried a `module` and an `app`, which the `update_app` patch had by then stamped
# onto every workspace with a module, site-created ones included.

import frappe


def execute():
	from frappe.model.sync import create_entity_file_map

	shipped = create_entity_file_map(["Workspace"])["Workspace"]
	if not shipped:
		return

	for name in frappe.get_all(
		"Workspace", filters={"public": 1, "standard": 0, "name": ["in", list(shipped)]}, pluck="name"
	):
		frappe.db.set_value("Workspace", name, "standard", 1, update_modified=False)
