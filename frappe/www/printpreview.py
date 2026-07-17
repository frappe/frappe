no_cache = 1


def get_context(context):
	import frappe
	from frappe.printing.doctype.print_format.classic_converter import (
		get_default_print_format,
		uses_beta_renderer,
	)
	from frappe.www.printview import get_print_format_doc

	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.name
	letterhead = frappe.form_dict.get("letterhead")
	settings = frappe.parse_json(frappe.form_dict.get("settings"))

	doc = frappe.get_doc(doctype, docname)
	pf = get_print_format_doc(frappe.form_dict.print_format, meta=doc.meta) or get_default_print_format(
		doctype
	)

	if uses_beta_renderer(pf):
		from frappe.utils.print_format_generator import get_html

		context.body = get_html(doctype, docname, pf, letterhead, settings=settings)
	else:
		context.body = pf.get_html(docname, letterhead)
