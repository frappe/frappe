import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'DocField')

	frappe.db.sql("""UPDATE tabDocField set options='DocType\nReport\nPage\nDashboard\nRoute' where parent LIKE 'Desk Shortcut' and fieldname LIKE 'type'""")

	frappe.clear_cache(doctype='DocField')
