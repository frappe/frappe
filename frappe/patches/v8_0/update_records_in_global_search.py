import frappe
from frappe.utils.global_search import get_doctypes_with_global_search, rebuild_for_doctype

def execute():
	frappe.cache().delete_value('doctypes_with_global_search')
	for doctype in get_doctypes_with_global_search(with_child_tables=False):
		rebuild_for_doctype(doctype)
