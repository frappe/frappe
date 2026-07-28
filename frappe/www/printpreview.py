no_cache = 1


def get_context(context):
	import frappe
	from frappe.www.printview import resolve_print_format

	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.name
	letterhead = frappe.form_dict.get("letterhead")
	settings = frappe.parse_json(frappe.form_dict.get("settings"))

	doc = frappe.get_doc(doctype, docname)
	pf, is_beta = resolve_print_format(frappe.form_dict.print_format, doc.meta)

	if is_beta:
		from frappe.utils.print_format_generator import get_html

		context.body = get_html(doctype, docname, pf, letterhead, settings=settings)
	else:
		context.body = pf.get_html(docname, letterhead)
