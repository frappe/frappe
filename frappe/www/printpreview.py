no_cache = 1


def get_context(context):
	import frappe

	print_format = frappe.form_dict.print_format
	docname = frappe.form_dict.name
	letterhead = frappe.form_dict.get("letterhead")

	from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

	pf = frappe.get_doc("Print Format", print_format)

	if uses_beta_renderer(pf):
		from frappe.utils.print_format_generator import get_html

		context.body = get_html(pf.doc_type, docname, print_format, letterhead)
	else:
		context.body = pf.get_html(docname, letterhead)
