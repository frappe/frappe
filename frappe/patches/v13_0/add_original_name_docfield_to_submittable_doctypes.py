import frappe
from frappe.database.schema import add_column

def execute():
	for doctype in frappe.db.get_all('DocType'):
		doctype = frappe.get_doc('DocType', doctype.name)
		if doctype.is_submittable and frappe.db.table_exists(doctype.name):
			doctype.make_cancellable()
			if not frappe.db.has_column(doctype.name, 'original_name'):
				add_column(doctype.name, 'original_name', 'Text')
			doctype.db_update_all()
