import frappe


def execute():
	if not frappe.db.exists("Flow Tool", "suggest_replies"):
		return
	frappe.db.delete("Flow Agent Tool", {"tool": "suggest_replies"})
	frappe.delete_doc("Flow Tool", "suggest_replies", ignore_permissions=True)
