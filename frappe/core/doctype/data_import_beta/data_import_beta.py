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
		if not self.import_file:
			self.import_json = ''

	def get_preview_from_template(self):
		if not self.import_file:
			return

		f = frappe.get_doc('File', { 'file_url': self.import_file })
		file_content = f.get_content()

		i = Importer(self.reference_doctype, content=file_content)
		import_options = frappe.parse_json(self.import_json or '{}')
		return i.get_data_for_import_preview(import_options)


@frappe.whitelist()
def download_template(doctype, export_fields=None, export_records=None, export_filters=None, file_type='CSV'):
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

	e = Exporter(doctype,
		export_fields=export_fields,
		export_data=True,
		export_filters=export_filters,
		file_type=file_type
	)
	e.build_csv_response()
