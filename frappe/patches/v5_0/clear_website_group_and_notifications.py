import frappe

def execute():
	frappe.delete_doc("DocType", "Post")
	frappe.delete_doc("DocType", "Website Group")
	frappe.delete_doc("DocType", "Website Route Permission")
	frappe.delete_doc("DocType", "User Vote")
	frappe.delete_doc("DocType", "Notification Count")
