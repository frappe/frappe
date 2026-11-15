from json import loads

import frappe
from frappe.desk.doctype.workspace.workspace import own_layout, site_edit
from frappe.desk.legacy_widgets import changes_from_copy


def execute():
	"""A v16 site's whole copy of a workspace, or a person's, becomes their layout of it."""
	if not frappe.db.has_column("Custom Workspace", "content"):
		return

	table = frappe.qb.DocType("Custom Workspace")
	copies = (
		frappe.qb.from_(table)
		.select(table.name, table.workspace, table.user, table.content, table.widgets)
		.where(table.content.isnotnull() & (table.content != ""))
		.run(as_dict=True)
	)
	for copy in copies:
		if frappe.db.exists("Workspace", copy.workspace):
			save_as_layout(copy)
		forget_copy(copy)


def save_as_layout(copy):
	base = frappe.get_doc("Workspace", copy.workspace)
	layout = own_layout(copy.workspace, copy.user) if copy.user else site_edit(copy.workspace)
	layout.changes = changes_from_copy(base, loads(copy.content), loads(copy.widgets or "{}"))
	layout.save()


def forget_copy(copy):
	if copy.user:
		frappe.db.delete("Custom Workspace", copy.name)
	else:
		table = frappe.qb.DocType("Custom Workspace")
		frappe.qb.update(table).set(table.content, None).set(table.widgets, None).where(
			table.name == copy.name
		).run()
