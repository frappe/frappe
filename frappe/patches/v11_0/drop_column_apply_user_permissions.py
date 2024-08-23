import frappe


def execute():
	column = "apply_user_permissions"
	to_remove = ["DocPerm", "Custom DocPerm"]

	for doctype in to_remove:
		if frappe.db.table_exists(doctype):
			if column in frappe.db.get_table_columns(doctype):
				frappe.db.sql(f"alter table `tab{doctype}` drop column {column}")

	frappe.reload_doc("core", "doctype", "docperm", force=True)
	frappe.reload_doc("core", "doctype", "custom_docperm", force=True)
