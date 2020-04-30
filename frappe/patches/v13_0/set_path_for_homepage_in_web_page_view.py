import frappe

def execute():
	frappe.reload_doctype('Web Page View')
	frappe.db.sql("""UPDATE `tabWeb Page View` set path="/" where path=''""")
