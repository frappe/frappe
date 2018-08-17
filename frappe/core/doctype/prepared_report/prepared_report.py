# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import base64
import json

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.desk.query_report import generate_report_result, get_columns_dict
from frappe.utils.file_manager import save_file, remove_all
from frappe.utils.csvutils import to_csv, read_csv_content_from_attached_file
from frappe.desk.form.load import get_attachments
from frappe.utils.file_manager import download_file


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
	result = generate_report_result(report, filters=json.loads(instance.filters), user=instance.owner)
	create_csv_file(remove_header_meta(result['columns']), result['result'], 'Prepared Report', instance.name)

	instance.status = "Completed"
	instance.report_end_time = frappe.utils.now()
	instance.save()

	frappe.publish_realtime(
		'report_generated',
		{"report_name": instance.report_name},
		user=frappe.session.user
	)


def remove_header_meta(columns):
	column_list = []
	columns_header = get_columns_dict(columns)
	for idx in range(len(columns)):
		column_list.append(columns_header[idx]['label'])
	return column_list


def create_csv_file(columns, data, dt, dn):
	csv_filename = '{0}.csv'.format(frappe.utils.data.format_datetime(frappe.utils.now(), "Y-m-d-H:M"))
	rows = [tuple(columns)] + data
	encoded = base64.b64encode(frappe.safe_encode(to_csv(rows)))
	# Call save_file function to upload and attach the file
	save_file(
		fname=csv_filename,
		content=encoded,
		dt=dt,
		dn=dn,
		folder=None,
		decode=True,
		is_private=False)


@frappe.whitelist()
def get_report_attachment_data(dn):

	doc = frappe.get_doc("Prepared Report", dn)
	data = read_csv_content_from_attached_file(doc)

	return {
		'columns': data[0],
		'result': data[1:]
	}


@frappe.whitelist()
def download_attachment(dn):
	attachment = get_attachments("Prepared Report", dn)[0]
	download_file(attachment.file_url)
