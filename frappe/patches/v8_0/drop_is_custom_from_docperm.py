from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype('DocPerm')
	if frappe.db.has_column('DocPerm', 'is_custom'):
		frappe.db.commit()
		frappe.db.sql('alter table `tabDocPerm` drop column is_custom')