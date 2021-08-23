import frappe

def execute():
	custom_doctypes = frappe.get_all('DocType', fields=['name', 'sort_field'])
 
	for doctype in custom_doctypes:
		if doctype.sort_field == 'modified':
			frappe.db.set_value('DocType', doctype.name, 'sort_field', 'creation', update_modified=False)

	frappe.db.commit()