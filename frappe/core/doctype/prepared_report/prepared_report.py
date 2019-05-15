# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import base64
import json

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.desk.query_report import generate_report_result
from frappe.utils.file_manager import save_file, remove_all
from frappe.desk.form.load import get_attachments
from frappe.utils.file_manager import get_file
from frappe.utils import gzip_compress, gzip_decompress

class PreparedReport(Document):

	def before_insert(self):
		self.status = "Queued"
		self.report_start_time = frappe.utils.now()

	def enqueue_report(self):
		enqueue(
			run_background,
			prepared_report=self.name, timeout=6000
		)

	def on_trash(self):
		remove_all("PreparedReport", self.name, from_delete=True)


def run_background(prepared_report):
	instance = frappe.get_doc("Prepared Report", prepared_report)
	report = frappe.get_doc("Report", instance.ref_report_doctype)

	try:
		report.custom_columns = []

		if report.report_type == 'Custom Report':
			custom_report_doc = report
			reference_report = custom_report_doc.reference_report
			report = frappe.get_doc("Report", reference_report)
			report.custom_columns = custom_report_doc.json

		result = generate_report_result(report, filters=instance.filters, user=instance.owner)
		create_json_gz_file(result['result'], 'Prepared Report', instance.name)

		instance.status = "Completed"
		instance.columns = json.dumps(result["columns"])
		instance.report_end_time = frappe.utils.now()
		instance.save(ignore_permissions=True)

	except Exception:
		frappe.log_error(frappe.get_traceback())
		instance = frappe.get_doc("Prepared Report", prepared_report)
		instance.status = "Error"
		instance.error_message = frappe.get_traceback()
		instance.save(ignore_permissions=True)

	frappe.publish_realtime(
		'report_generated',
		{"report_name": instance.report_name, "name": instance.name},
		user=frappe.session.user
	)


def create_json_gz_file(data, dt, dn):
	# Storing data in CSV file causes information loss
	# Reports like P&L Statement were completely unsuable because of this
	json_filename = '{0}.json.gz'.format(frappe.utils.data.format_datetime(frappe.utils.now(), "Y-m-d-H:M"))
	encoded_content = frappe.safe_encode(frappe.as_json(data))

	# GZip compression seems to reduce storage requirements by 80-90%
	compressed_content = gzip_compress(encoded_content)
	save_file(
		fname=json_filename,
		content=compressed_content,
		dt=dt,
		dn=dn,
		folder=None,
		is_private=False)


@frappe.whitelist()
def download_attachment(dn):
	attachment = get_attachments("Prepared Report", dn)[0]
	frappe.local.response.filename = attachment.file_name[:-2]
	frappe.local.response.filecontent = gzip_decompress(get_file(attachment.name)[1])
	frappe.local.response.type = "binary"
