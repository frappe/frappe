import frappe

def execute():
	for doctype in frappe.db.get_all('DocType'):
		doctype = frappe.get_meta(doctype.name)
		if doctype.is_submittable and frappe.db.table_exists(doctype.name):
			doctype.make_cancellable()
			frappe.reload_doctype(doctype.name)
			doctype.db_update_all()
