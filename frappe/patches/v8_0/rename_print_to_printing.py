import frappe

def execute():
	if frappe.db.exists('Module Def', 'Print'):
		frappe.reload_doc('printing', 'doctype', 'print_format')
		frappe.reload_doc('printing', 'doctype', 'print_settings')
		frappe.reload_doc('printing', 'doctype', 'print_heading')
		frappe.reload_doc('printing', 'doctype', 'letter_head')
		frappe.reload_doc('printing', 'page', 'print_format_builder')
		frappe.db.sql("""update `tabPrint Format` set module='Printing' where module='Print'""")
		
		frappe.delete_doc('Module Def', 'Print')