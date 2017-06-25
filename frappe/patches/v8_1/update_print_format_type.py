import frappe

def execute():
	frappe.db.sql("""
		UPDATE
			`tabPrint Format`
		SET
			type='DocType'
	""")