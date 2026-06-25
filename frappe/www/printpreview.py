no_cache = 1


def get_context(context):
	import frappe

	print_format = frappe.form_dict.print_format
	docname = frappe.form_dict.name
	letterhead = frappe.form_dict.get("letterhead")

	pf = frappe.get_doc("Print Format", print_format)

	if pf.get("print_format_builder_beta") and pf.get("format_data"):
		from frappe.utils.print_format_generator import get_html

		context.body = get_html(pf.doc_type, docname, print_format, letterhead)
	else:
		context.body = pf.get_html(docname, letterhead)
