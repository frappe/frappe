import frappe


def execute() -> None:
	frappe.reload_doc("workflow", "doctype", "workflow_transition")
	frappe.db.sql("update `tabWorkflow Transition` set allow_self_approval=1")
