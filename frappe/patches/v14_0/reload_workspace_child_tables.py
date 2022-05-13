import frappe
from frappe.modules import get_doctype_module


def execute():
	child_tables = [
		r[0]
		for r in frappe.get_all(
			"DocField",
			fields="options",
			filters={"fieldtype": ["in", frappe.model.table_fields], "parent": "Workspace"},
			as_list=1,
		)
	]

	for child_table in child_tables:
		module = get_doctype_module(child_table).lower()
		frappe.reload_doc(module, "doctype", child_table, force=True)
