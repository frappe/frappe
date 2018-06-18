# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import StringIO
import csv
import base64
import json

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.desk.query_report import generate_report_result
from frappe.utils.file_manager import save_file


class BackgroundReportResult(Document):
	def after_insert(self):
		enqueue(
			run_background,
			self=self, timeout=6000
		)


@frappe.whitelist()
def run_background(self):
	report = frappe.get_doc("Report", self.ref_report_doctype)
	result = generate_report_result(report, filters=json.loads(self.filters), user=self.owner)
	create_csv_file(result['columns'], result['result'], 'Background Report Result', self.name)
	self.status = "Completed"
	self.report_end_time = frappe.utils.now()
	self.save()


@frappe.whitelist()
def create_csv_file(columns, data, dt, dn):
	# create the list of column labels
	column_list = [str(d) for d in columns]
	csv_filename = '{0}.csv'.format(frappe.utils.data.format_datetime(frappe.utils.now(), "Y-m-d-H:M"))
	# Write columns and results to string
	out = StringIO.StringIO()
	csv_out = csv.writer(out)
	csv_out.writerow(column_list)
	for row in data:
		csv_out.writerow(row)
	# encode the content of csv
	encoded = base64.b64encode(out.getvalue())
	# Call save_file function to upload and attahc the file
	save_file(
		fname=csv_filename,
		content=encoded,
		dt=dt,
		dn=dn,
		folder=None,
		decode=True,
		is_private=False)



