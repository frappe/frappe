no_cache = 1


def get_context(context):
	import frappe
	from frappe.utils.jinja_globals import is_rtl
	from frappe.www.printview import get_print_style, get_rendered_template, resolve_print_format

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
		# Jinja formats render through the legacy pipeline, wrapped in the same
		# page shell /printview uses — PrintFormat.get_html is the beta generator
		# and has nothing to draw for them
		body = get_rendered_template(
			doc, print_format=pf, meta=doc.meta, letterhead=letterhead, settings=settings
		)
		context.body = frappe.render_template(
			"www/printview.html",
			{
				"standalone": False,
				"no_action_banner": True,
				"body": body,
				"print_style": get_print_style(print_format=pf),
				"lang": frappe.local.lang,
				"layout_direction": "rtl" if is_rtl() else "ltr",
				"title": doc.get_title() or doc.name,
				"comment": None,
			},
		)
