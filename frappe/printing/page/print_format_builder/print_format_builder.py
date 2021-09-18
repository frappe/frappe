import frappe

@frappe.whitelist()
def create_custom_format(doctype, name, based_on='Standard'):
	doc = frappe.new_doc('Print Format')
	doc.doc_type = doctype
	doc.name = name
	doc.print_format_builder = 1
	doc.format_data = frappe.db.get_value('Print Format', based_on, 'format_data') \
		if based_on != 'Standard' else None
	doc.insert()
	return doc