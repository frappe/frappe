no_cache = 1


def get_context(context):
	import frappe
	from frappe.utils.print_format_generator import get_html

	print_format = frappe.form_dict.print_format
	docname = frappe.form_dict.name
	letterhead = frappe.form_dict.get("letterhead")

	pf = frappe.get_doc("Print Format", print_format)
	context.body = get_html(pf.doc_type, docname, print_format, letterhead)
