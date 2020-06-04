# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import calendar
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (format_time, get_link_to_form, get_url_to_report,
	global_date_format, now, now_datetime, validate_email_address, today, add_to_date)
from frappe.model.naming import append_number_if_name_exists
from frappe.utils.csvutils import to_csv
from frappe.utils.xlsxutils import make_xlsx

max_reports_per_user = frappe.local.conf.max_reports_per_user or 3


class AutoEmailReport(Document):
	def autoname(self):
		self.name = _(self.report)
		if frappe.db.exists('Auto Email Report', self.name):
			self.name = append_number_if_name_exists('Auto Email Report', self.name)

	def validate(self):
		self.validate_report_count()
		self.validate_emails()
		self.validate_report_format()

	def validate_emails(self):
		'''Cleanup list of emails'''
		if ',' in self.email_to:
			self.email_to.replace(',', '\n')

		valid = []
		for email in self.email_to.split():
			if email:
				validate_email_address(email, True)
				valid.append(email)

		self.email_to = '\n'.join(valid)

	def validate_report_count(self):
		'''check that there are only 3 enabled reports per user'''
		count = frappe.db.sql('select count(*) from `tabAuto Email Report` where user=%s and enabled=1', self.user)[0][0]
		if count > max_reports_per_user + (-1 if self.flags.in_insert else 0):
			frappe.throw(_('Only {0} emailed reports are allowed per user').format(max_reports_per_user))

	def validate_report_format(self):
		""" check if user has select correct report format """
		valid_report_formats = ["HTML", "XLSX", "CSV"]
		if self.format not in valid_report_formats:
			frappe.throw(_("{0} is not a valid report format. Report format should one of the following {1}")
				.format(frappe.bold(self.format), frappe.bold(", ".join(valid_report_formats))))

	def get_report_content(self):
		'''Returns file in for the report in given format'''
		report = frappe.get_doc('Report', self.report)

		self.filters = frappe.parse_json(self.filters) if self.filters else {}

		if self.report_type=='Report Builder' and self.data_modified_till:
			self.filters['modified'] = ('>', now_datetime() - timedelta(hours=self.data_modified_till))

		if self.report_type != 'Report Builder' and self.dynamic_date_filters_set():
			self.prepare_dynamic_filters()

		columns, data = report.get_data(limit=self.no_of_rows or 100, user = self.user,
			filters = self.filters, as_dict=True, ignore_prepared_report=True)

		# add serial numbers
		columns.insert(0, frappe._dict(fieldname='idx', label='', width='30px'))
		for i in range(len(data)):
			data[i]['idx'] = i+1

		if len(data)==0 and self.send_if_data:
			return None

		if self.format == 'HTML':
			columns, data = make_links(columns, data)

			return self.get_html_table(columns, data)

		elif self.format == 'XLSX':
			spreadsheet_data = self.get_spreadsheet_data(columns, data)
			xlsx_file = make_xlsx(spreadsheet_data, "Auto Email Report")
			return xlsx_file.getvalue()

		elif self.format == 'CSV':
			spreadsheet_data = self.get_spreadsheet_data(columns, data)
			return to_csv(spreadsheet_data)

		else:
			frappe.throw(_('Invalid Output Format'))

	def get_html_table(self, columns=None, data=None):

		date_time = global_date_format(now()) + ' ' + format_time(now())
		report_doctype = frappe.db.get_value('Report', self.report, 'ref_doctype')

		return frappe.render_template('frappe/templates/emails/auto_email_report.html', {
			'title': self.name,
			'description': self.description,
			'date_time': date_time,
			'columns': columns,
			'data': data,
			'report_url': get_url_to_report(self.report, self.report_type, report_doctype),
			'report_name': self.report,
			'edit_report_settings': get_link_to_form('Auto Email Report', self.name)
		})

	@staticmethod
	def get_spreadsheet_data(columns, data):
		out = [[_(df.label) for df in columns], ]
		for row in data:
			new_row = []
			out.append(new_row)
			for df in columns:
				if df.fieldname not in row: continue
				new_row.append(frappe.format(row[df.fieldname], df, row))

		return out

	def get_file_name(self):
		return "{0}.{1}".format(self.report.replace(" ", "-").replace("/", "-"), self.format.lower())

	def prepare_dynamic_filters(self):
		self.filters = frappe.parse_json(self.filters)

		to_date = today()
		from_date_value = {
			'Daily': ('days', -1),
			'Weekly': ('weeks', -1),
			'Monthly': ('months', -1),
			'Quarterly': ('months', -3),
			'Half Yearly': ('months', -6),
			'Yearly': ('years', -1)
		}[self.dynamic_date_period]

		from_date = add_to_date(to_date, **{from_date_value[0]: from_date_value[1]})

		self.filters[self.from_date_field] = from_date
		self.filters[self.to_date_field] = to_date

	def send(self):
		if self.filter_meta and not self.filters:
			frappe.throw(_("Please set filters value in Report Filter table."))

		data = self.get_report_content()
		if not data:
			return

		attachments = None
		if self.format == "HTML":
			message = data
		else:
			message = self.get_html_table()

		if not self.format=='HTML':
			attachments = [{
				'fname': self.get_file_name(),
				'fcontent': data
			}]

		frappe.sendmail(
			recipients = self.email_to.split(),
			subject = self.name,
			message = message,
			attachments = attachments,
			reference_doctype = self.doctype,
			reference_name = self.name
		)

	def dynamic_date_filters_set(self):
		return self.dynamic_date_period and self.from_date_field and self.to_date_field

@frappe.whitelist()
def download(name):
	'''Download report locally'''
	auto_email_report = frappe.get_doc('Auto Email Report', name)
	auto_email_report.check_permission()
	data = auto_email_report.get_report_content()

	if not data:
		frappe.msgprint(_('No Data'))
		return

	frappe.local.response.filecontent = data
	frappe.local.response.type = "download"
	frappe.local.response.filename = auto_email_report.get_file_name()

@frappe.whitelist()
def send_now(name):
	'''Send Auto Email report now'''
	auto_email_report = frappe.get_doc('Auto Email Report', name)
	auto_email_report.check_permission()
	auto_email_report.send()

def send_daily():
	'''Check reports to be sent daily'''

	current_day = calendar.day_name[now_datetime().weekday()]
	enabled_reports = frappe.get_all('Auto Email Report',
		filters={'enabled': 1, 'frequency': ('in', ('Daily', 'Weekdays', 'Weekly'))})

	for report in enabled_reports:
		auto_email_report = frappe.get_doc('Auto Email Report', report.name)

		# if not correct weekday, skip
		if auto_email_report.frequency == "Weekdays":
			if current_day in ("Saturday", "Sunday"):
				continue
		elif auto_email_report.frequency == 'Weekly':
			if auto_email_report.day_of_week != current_day:
				continue
		try:
			auto_email_report.send()
		except Exception as e:
			frappe.log_error(e, _('Failed to send {0} Auto Email Report').format(auto_email_report.name))


def send_monthly():
	'''Check reports to be sent monthly'''
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': 'Monthly'}):
		frappe.get_doc('Auto Email Report', report.name).send()

def make_links(columns, data):
	for row in data:
		for col in columns:
			if col.fieldtype == "Link" and col.options != "Currency":
				if col.options and row.get(col.fieldname):
					row[col.fieldname] = get_link_to_form(col.options, row[col.fieldname])
			elif col.fieldtype == "Dynamic Link":
				if col.options and row.get(col.fieldname) and row.get(col.options):
					row[col.fieldname] = get_link_to_form(row[col.options], row[col.fieldname])

	return columns, data
