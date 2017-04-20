def execute():
	from frappe.website.router import get_doctypes_with_web_view
	from frappe.utils.global_search import rebuild_for_doctype

	for doctype in get_doctypes_with_web_view():
		rebuild_for_doctype(doctype)
