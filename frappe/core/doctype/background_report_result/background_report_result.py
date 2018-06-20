# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import csv
import base64
import json

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.desk.query_report import generate_report_result, get_columns_dict
from frappe.utils.file_manager import save_file
from io import BytesIO


class BackgroundReportResult(Document):

	def before_insert(self):
		self.status = "Queued"
		self.report_start_time = frappe.utils.now()

	def after_insert(self):
		enqueue(
			run_background,
			instance=self, timeout=6000
		)


def run_background(instance):
	report = frappe.get_doc("Report", instance.ref_report_doctype)
	result = generate_report_result(report, filters=json.loads(instance.filters), user=instance.owner)
	create_csv_file(result['columns'], result['result'], 'Background Report Result', instance.name)
	instance.status = "Completed"
	instance.report_end_time = frappe.utils.now()
	instance.save()


def create_csv_file(columns, data, dt, dn):
	# create the list of column labels
	column_list = []
	columns_header = get_columns_dict(columns)
	for idx in range(len(columns)):
		column_list.append(columns_header[idx]["label"])
	csv_filename = '{0}.csv'.format(frappe.utils.data.format_datetime(frappe.utils.now(), "Y-m-d-H:M"))
	# Write columns and results to string
	out = BytesIO()
	csv_out = csv.writer(out)
	csv_out.writerow(column_list)
	for row in data:
		csv_out.writerow(row)
	# encode the content of csv
	encoded = base64.b64encode(out.getvalue())
	# Call save_file function to upload and attach the file
	save_file(
		fname=csv_filename,
		content=encoded,
		dt=dt,
		dn=dn,
		folder=None,
		decode=True,
		is_private=False)
