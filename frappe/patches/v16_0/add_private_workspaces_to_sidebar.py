import click

import frappe


def execute():
	from frappe.query_builder import DocType

	workspace = DocType("Workspace")
	all_workspaces = (frappe.qb.from_(workspace).select(workspace.name).where(workspace.public == 0)).run(
		pluck=True
	)
	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import add_to_my_workspace

	for space in all_workspaces:
		workspace_doc = frappe.get_doc("Workspace", space)
		add_to_my_workspace(workspace_doc)
	# save the sidebar items
	frappe.db.commit()  # nosemgrep
