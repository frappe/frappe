import frappe

def execute():
	frappe.reload_doc("core", "doctype", "communication")
	frappe.reload_doc("core", "doctype", "activity_log")

	frappe.db.sql("""insert into `tabActivity Log` (name, owner, modified, creation, status, communication_date,
			reference_doctype, reference_name, timeline_doctype, timeline_name, link_doctype, link_name, subject, content, user)
			select name, owner, modified, creation, status, communication_date,
			reference_doctype, reference_name, timeline_doctype, timeline_name, link_doctype, link_name, subject, content, user
			from `tabCommunication`
			where comment_type = 'Updated'""")

	frappe.db.sql("""delete from `tabCommunication` where comment_type = 'Updated'""")
	frappe.delete_doc("DocType", "Authentication Log")
