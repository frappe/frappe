import frappe


def execute():
	Workspace = frappe.qb.DocType("Workspace")
	frappe.qb.update(Workspace).set(Workspace.renderer, "Frappe UI").run()
