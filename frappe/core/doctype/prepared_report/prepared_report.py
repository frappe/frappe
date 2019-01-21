# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import base64
import json
import io

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.desk.query_report import generate_report_result, get_columns_dict
from frappe.core.doctype.file.file import remove_all
from frappe.utils.csvutils import to_csv, read_csv_content_from_attached_file
from frappe.desk.form.load import get_attachments
from frappe.utils import gzip_compress, gzip_decompress
from six import PY2
from frappe.utils import encode

class PreparedReport(Document):

	def before_insert(self):
		self.status = "Queued"
		self.report_start_time = frappe.utils.now()

	def after_insert(self):
		enqueue(
			run_background,
			instance=self, timeout=6000
		)

	def on_trash(self):
		remove_all("PreparedReport", self.name, from_delete=True)


def run_background(instance):
	report = frappe.get_doc("Report", instance.ref_report_doctype)
	result = generate_report_result(report, filters=instance.filters, user=instance.owner)
	create_json_gz_file(result['result'], 'Prepared Report', instance.name)

	instance.status = "Completed"
	instance.columns = json.dumps(result["columns"])
	instance.report_end_time = frappe.utils.now()
	instance.save()

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
	compressed_content = gzip_compress(encoded_content)

	# Call save() file function to upload and attach the file
	_file = frappe.get_doc({
		"doctype": "File",
		"file_name": json_filename,
		"attached_to_doctype": dt,
		"attached_to_name": dn,
		"content": compressed_content
	})
	_file.save()

@frappe.whitelist()
def download_attachment(dn):
	attachment = get_attachments("Prepared Report", dn)[0]
	frappe.local.response.filename = attachment.file_name[:-2]
	attached_file = frappe.get_doc('File', attachment.name)
	frappe.local.response.filecontent = gzip_decompress(attached_file.get_content())
	frappe.local.response.type = "binary"
