import frappe

def execute():
	frappe.reload_doc("contacts", "doctype", "contact_phone")
	frappe.reload_doc("contacts", "doctype", "contact")

	frappe.db.sql("""UPDATE `tabContact Phone` SET is_primary_mobile_no='1' WHERE idx='2'""")