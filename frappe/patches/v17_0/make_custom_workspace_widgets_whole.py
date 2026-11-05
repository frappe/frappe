from json import dumps, loads

import frappe
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	_prune_widgets,
	merge_widgets,
	snapshot_widgets,
)


def execute():
	"""A site layout's `widgets` held only the widgets the site added; it now holds the whole set."""
	for name in frappe.get_all(
		"Custom Workspace", filters={"user": ("is", "not set"), "content": ("is", "set")}, pluck="name"
	):
		row = frappe.get_doc("Custom Workspace", name)
		if not frappe.db.exists("Workspace", row.workspace):
			continue
		base = frappe.get_doc("Workspace", row.workspace)
		widgets = merge_widgets(snapshot_widgets(base), loads(row.widgets or "{}"))
		row.db_set("widgets", dumps(_prune_widgets(widgets, loads(row.content))), update_modified=False)
