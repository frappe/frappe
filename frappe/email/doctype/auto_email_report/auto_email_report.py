# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import calendar
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (get_link_to_form, now, now_datetime, validate_email_address, today)

from frappe.utils.report_rendering import (get_report_content, get_html_table)

max_reports_per_user = frappe.local.conf.max_reports_per_user or 3


class AutoEmailReport(Document):
	def autoname(self):
		self.name = _(self.report)

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
			frappe.throw(_("%s is not a valid report format. Report format should \
				one of the following %s"%(frappe.bold(self.format), frappe.bold(", ".join(valid_report_formats)))))

	def get_file_name(self):
		return "{0}.{1}".format(self.report.replace(" ", "-").replace("/", "-"), self.format.lower())
	
	def send(self):
		if self.filter_meta and not self.filters:
			frappe.throw(_("Please set filters value in Report Filter table."))

		if self.filters:
			self.filters = frappe.parse_json(self.filters)
		data = get_report_content(self.report,
					self.filters, 
					self.format, 
					self.no_of_rows, 
					self.description, 
					self.user, 
					self.data_modified_till, 
					self.from_date_field, 
					self.to_date_field, 
					self.dynamic_date_period, 
					additional_params = {
						'single_report': 1, 
						'edit_report_settings': get_link_to_form('Auto Email Report', self.name)
						}
				)
		if not data:
			return

		attachments = None
		if self.format == "HTML":
			message = data
		else:
			message = self.get_html_table(report_name=self.report, report_type=self.report_type, description=self.description)

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

@frappe.whitelist()
def download(name):
	'''Download report locally'''
	auto_email_report = frappe.get_doc('Auto Email Report', name)
	auto_email_report.check_permission()
	if auto_email_report.filters:
		auto_email_report.filters = frappe.parse_json(auto_email_report.filters)
	data = get_report_content(
		auto_email_report.report, 
		auto_email_report.filters,
		auto_email_report.format,
		auto_email_report.no_of_rows, 
		auto_email_report.description, 
		auto_email_report.user, 
		auto_email_report.data_modified_till, 
		auto_email_report.from_date_field, 
		auto_email_report.to_date_field, 
		auto_email_report.dynamic_date_period, 
		additional_params = {
			'edit_report_settings': get_link_to_form('Auto Email Report', auto_email_report.name)
			}
		)
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

		auto_email_report.send()


def send_monthly():
	'''Check reports to be sent monthly'''
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': 'Monthly'}):
		frappe.get_doc('Auto Email Report', report.name).send()

