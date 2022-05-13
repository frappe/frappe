import frappe


def execute():
	child_tables = frappe.get_all(
		"DocField",
		pluck="options",
		filters={"fieldtype": ["in", frappe.model.table_fields], "parent": "Workspace"},
	)

	for child_table in child_tables:
		if child_table != "Has Role":
			frappe.reload_doc("desk", "doctype", child_table, force=True)
