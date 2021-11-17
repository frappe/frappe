# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files

class FormTour(Document):
	def before_insert(self):
		if not self.is_standard:
			return

		# while syncing, set proper docfield reference
		for d in self.steps:
			if not frappe.db.exists('DocField', d.field):
				d.field = frappe.db.get_value('DocField', {
					'fieldname': d.fieldname, 'parent': self.reference_doctype, 'fieldtype': d.fieldtype
				}, "name")

			if d.is_table_field and not frappe.db.exists('DocField', d.parent_field):
				d.parent_field = frappe.db.get_value('DocField', {
					'fieldname': d.parent_fieldname, 'parent': self.reference_doctype, 'fieldtype': 'Table'
				}, "name")

	def on_update(self):
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files([['Form Tour', self.name]], self.module)

	def before_export(self, doc):
		for d in doc.steps:
			d.field = ""
			d.parent_field = ""

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_docfield_list(doctype, txt, searchfield, start, page_len, filters):
	or_filters = [
		['fieldname', 'like', '%' + txt + '%'],
		['label', 'like', '%' + txt + '%'],
		['fieldtype', 'like', '%' + txt + '%']
	]

	parent_doctype = filters.get('doctype')
	fieldtype = filters.get('fieldtype')
	if not fieldtype:
		excluded_fieldtypes = ['Column Break']
		excluded_fieldtypes += filters.get('excluded_fieldtypes', [])
		fieldtype_filter = ['not in', excluded_fieldtypes]
	else:
		fieldtype_filter = fieldtype

	docfields = frappe.get_all(
		doctype,
		fields=["name as value", "label", "fieldtype"],
		filters={'parent': parent_doctype, 'fieldtype': fieldtype_filter},
		or_filters=or_filters,
		limit_start=start,
		limit_page_length=page_len,
		order_by="idx",
		as_list=1,
	)
	return docfields
