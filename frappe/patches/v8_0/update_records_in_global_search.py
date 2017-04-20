def execute():
	from frappe.utils.global_search import get_doctypes_with_global_search, rebuild_for_doctype

	for doctype in get_doctypes_with_global_search():
		rebuild_for_doctype(doctype)
