# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.data_import.importer_new import Importer
from frappe.core.doctype.data_import.exporter_new import Exporter


class DataImportBeta(Document):
	def validate(self):
		doc_before_save = self.get_doc_before_save()
		if not self.import_file or (
			doc_before_save and doc_before_save.import_file != self.import_file
		):
			self.template_options = ""

	def get_preview_from_template(self):
		if not self.import_file:
			return

		i = self.get_importer()
		return i.get_data_for_import_preview()

	def start_import(self):
		i = self.get_importer()
		return i.import_data()

	def get_importer(self):
		return Importer(self.reference_doctype, data_import=self)

	def create_missing_link_values(self, missing_link_values):
		docs = []
		for d in missing_link_values:
			d = frappe._dict(d)
			if not d.has_one_mandatory_field:
				continue

			doctype = d.doctype
			values = d.missing_values
			meta = frappe.get_meta(doctype)
			# find the autoname field
			if meta.autoname and meta.autoname.startswith('field:'):
				autoname_field = meta.autoname[len('field:') :]
			else:
				autoname_field = 'name'

			for value in values:
				new_doc = frappe.new_doc(doctype)
				new_doc.set(autoname_field, value)
				docs.append(new_doc.insert())
		return docs

@frappe.whitelist()
def download_template(doctype, export_fields=None, export_records=None, export_filters=None, file_type="CSV"):
	"""
	Download template from Exporter
		:param doctype: Document Type
		:param export_fields=None: Fields to export as dict {'Sales Invoice': ['name', 'customer'], 'Sales Invoice Item': ['item_code']}
		:param export_records=None: One of 'all', 'last_10_records', 'by_filter'
		:param export_filters: Filter dict
		:param file_type: File type to export into
	"""

	export_fields = frappe.parse_json(export_fields)
	export_filters = frappe.parse_json(export_filters)

	e = Exporter(
		doctype,
		export_fields=export_fields,
		export_data=True,
		export_filters=export_filters,
		file_type=file_type,
	)
	e.build_csv_response()
