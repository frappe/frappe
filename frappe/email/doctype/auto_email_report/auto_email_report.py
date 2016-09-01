# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import frappe.utils

max_reports_per_user = 3

class AutoEmailReport(Document):
	def autoname(self):
		self.name = _(self.report)

	def validate(self):
		self.validate_report_count()
		self.validate_emails()

	def validate_emails(self):
		'''Cleanup list of emails'''
		if ',' in self.emails:
			self.emails.replace(',', '\n')

		valid = []
		for email in self.emails.split():
			if email:
				frappe.utils.validate_email_add(email, True)
				valid.append(email)

		self.emails = '\n'.join(valid)

	def validate_report_count(self):
		'''check that there are only 3 enabled reports per user'''
		count = frappe.db.sql('select count(*) from `tabAuto Email Report` where user=%s and enabled=1', self.user)[0][0]
		if count > max_reports_per_user:
			frappe.throw(_('Only {0} emailed reports are allowed per user').format(max_reports_per_user))

	def send(self):
		report = frappe.get_doc('Report', self.report)
		data = report.get_data(limit=500, user = self.user, filters = self.filters)

		message = '<p>{0}</p>'.format(_('{0} generated on {1}').format(self.name,
				frappe.utils.format_datetime(frappe.utils.now_datetime())))
		attachments = None

		if self.report_format == 'HTML':
			message += self.get_html_table(data)

		if self.report_format == 'XLS':
			attachments.append(self.get_xls())

		frappe.sendmail(
			recipients = self.emails.split(),
			subject = self.name,
			message = message,
			attachments = attachments
		)

	def get_html_table(self, data):
		return ''

	def get_csv(self, data):
		return

	def get_xls(self, data):
		return

def send_daily():
	'''Check reports to be sent daily'''
	now = frappe.utils.now_datetime()
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': ('in', ('Daily', 'Weekly'))}):
		auto_email_report = frappe.get_doc('Auto Email Report', report.name)
		if auto_email_report.frequency=='Weekly':
			# if not correct weekday, skip
			if now.weekday()!={'Monday':0,'Tuesday':1,'Wednesday':2,
				'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}[auto_email_report.weekday]:
				continue

			auto_email_report.send()

def send_monthly():
	'''Check reports to be sent monthly'''
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': 'Monthly'}):
		frappe.get_doc('Auto Email Report', report.name).send()
