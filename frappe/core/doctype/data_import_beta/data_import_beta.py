# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.data_import.importer_new import Importer
from frappe.core.doctype.data_import.exporter_new import Exporter
from frappe.core.page.background_jobs.background_jobs import get_info
from frappe.utils.background_jobs import enqueue
from frappe import _


class DataImportBeta(Document):
	def validate(self):
		doc_before_save = self.get_doc_before_save()
		if not self.import_file or (
			doc_before_save and doc_before_save.import_file != self.import_file
		):
			self.template_options = ""
			self.template_warnings = ""

		if self.import_file:
			# validate template
			self.get_importer()

	def get_preview_from_template(self):
		if not self.import_file:
			return

		i = self.get_importer()
		return i.get_data_for_import_preview()

	def start_import(self):
		if frappe.utils.scheduler.is_scheduler_inactive():
			frappe.throw(
				_("Scheduler is inactive. Cannot import data."), title=_("Scheduler Inactive")
			)

		enqueued_jobs = [d.get("job_name") for d in get_info()]

		if self.name not in enqueued_jobs:
			enqueue(
				start_import,
				queue="default",
				timeout=6000,
				event="data_import",
				job_name=self.name,
				data_import=self.name,
				now=frappe.conf.developer_mode or frappe.flags.in_test,
			)
			return True

		return False

	def export_errored_rows(self):
		return self.get_importer().export_errored_rows()

	def get_importer(self):
		return Importer(self.reference_doctype, data_import=self)


def start_import(data_import):
	"""This method runs in background job"""
	data_import = frappe.get_doc("Data Import Beta", data_import)
	try:
		i = Importer(data_import.reference_doctype, data_import=data_import)
		i.import_data()
	except:
		frappe.db.rollback()
		data_import.db_set('status', 'Error')
		frappe.log_error(title=data_import.name)
		frappe.db.commit()
		frappe.publish_realtime(
			"data_import_refresh", {"data_import": data_import.name}
		)

@frappe.whitelist()
def download_template(
	doctype, export_fields=None, export_records=None, export_filters=None, file_type="CSV"
):
	"""
	Download template from Exporter
		:param doctype: Document Type
		:param export_fields=None: Fields to export as dict {'Sales Invoice': ['name', 'customer'], 'Sales Invoice Item': ['item_code']}
		:param export_records=None: One of 'all', 'by_filter', 'blank_template'
		:param export_filters: Filter dict
		:param file_type: File type to export into
	"""

	export_fields = frappe.parse_json(export_fields)
	export_filters = frappe.parse_json(export_filters)
	export_data = export_records != "blank_template"

	e = Exporter(
		doctype,
		export_fields=export_fields,
		export_data=export_data,
		export_filters=export_filters,
		file_type=file_type,
		export_page_length=5 if export_records == "5_records" else None,
	)
	e.build_response()


@frappe.whitelist()
def download_errored_template(data_import_name):
	data_import = frappe.get_doc("Data Import Beta", data_import_name)
	data_import.export_errored_rows()
