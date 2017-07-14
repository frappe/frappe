import frappe

def execute():
	frappe.db.sql("""delete from `tabCustom DocPerm`
		where parent not in ( select name from `tabDocType` )
	""")
