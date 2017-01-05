import frappe

def execute():
	frappe.reload_doc('custom', 'doctype', 'custom_field', force=True)
	try:
		frappe.db.sql('update `tabCustom Field` set in_standard_filter = in_filter_dash`')
	except Exception, e:
		if e.args[0]!=1054: raise e
