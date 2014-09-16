import frappe

def execute():
	frappe.reload_doc("core", "doctype", "communication")
	frappe.db.sql("""update tabCommunication set reference_doctype = parenttype, reference_name = parent""")
