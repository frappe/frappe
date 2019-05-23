import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'doctype')
	frappe.db.commit()

	frappe.model.delete_fields({
		'DocType': ['hide_heading', 'image_view', 'read_only_onload']
	}, delete=1)

	frappe.db.sql('''
		DELETE from `tabProperty Setter`
		WHERE property = 'read_only_onload'
	''')
