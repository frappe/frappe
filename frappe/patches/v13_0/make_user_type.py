import frappe
from frappe.utils.install import create_user_type

def execute():
	frappe.reload_doc('core', 'doctype', 'role')
	frappe.reload_doc('core', 'doctype', 'user_document_type')
	frappe.reload_doc('core', 'doctype', 'user_type_module')
	frappe.reload_doc('core', 'doctype', 'user_select_document_type')
	frappe.reload_doc('core', 'doctype', 'user_type')


	create_user_type()
