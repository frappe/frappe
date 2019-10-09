from __future__ import unicode_literals
import frappe

def execute():
	if frappe.db.has_column('DocType', 'in_dialog'):
		frappe.db.sql('alter table tabDocType drop column in_dialog')
	frappe.clear_cache(doctype="DocType")