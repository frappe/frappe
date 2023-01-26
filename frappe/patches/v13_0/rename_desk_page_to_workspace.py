import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	if frappe.db.exists("DocType", "Desk Page"):
		if frappe.db.exists("DocType", "Workspace"):
			# this patch was not added initially, so this page might still exist
			frappe.delete_doc("DocType", "Desk Page")
		else:
			frappe.flags.ignore_route_conflict_validation = True
			rename_doc("DocType", "Desk Page", "Workspace")
			frappe.flags.ignore_route_conflict_validation = False

	rename_doc("DocType", "Desk Chart", "Workspace Chart", ignore_if_exists=True)
	rename_doc("DocType", "Desk Shortcut", "Workspace Shortcut", ignore_if_exists=True)
	rename_doc("DocType", "Desk Link", "Workspace Link", ignore_if_exists=True)

	frappe.reload_doc("desk", "doctype", "workspace", force=True)
	frappe.reload_doc("desk", "doctype", "workspace_link", force=True)
	frappe.reload_doc("desk", "doctype", "workspace_chart", force=True)
	frappe.reload_doc("desk", "doctype", "workspace_shortcut", force=True)
