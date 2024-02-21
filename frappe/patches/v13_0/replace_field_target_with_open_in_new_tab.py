import frappe


def execute():
	doctype = "Top Bar Item"
	if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, "target"):
		return

	frappe.reload_doc("website", "doctype", "top_bar_item")
	frappe.db.set_value(doctype, {"target": 'target = "_blank"'}, "open_in_new_tab", 1)
