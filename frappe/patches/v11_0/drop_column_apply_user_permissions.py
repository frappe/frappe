from __future__ import unicode_literals
import frappe

def execute():
	column = 'apply_user_permissions'
	to_remove = ['DocPerm', 'Custom DocPerm']

	for doctype in to_remove:
		if column in frappe.db.get_table_columns(doctype):
			frappe.db.sql("alter table `tab{0}` drop column {1}".format(doctype, column))

	frappe.reload_doc('core', 'doctype', 'docperm', force=True)
	frappe.reload_doc('core', 'doctype', 'custom_docperm', force=True)

