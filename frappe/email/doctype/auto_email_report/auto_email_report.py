# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import frappe.utils
from frappe.utils.xlsutils import get_xls
from frappe.utils.csvutils import to_csv

max_reports_per_user = 3

class AutoEmailReport(Document):
	def autoname(self):
		self.name = _(self.report)

	def validate(self):
		self.validate_report_count()
		self.validate_emails()

	def validate_emails(self):
		'''Cleanup list of emails'''
		if ',' in self.email_to:
			self.email_to.replace(',', '\n')

		valid = []
		for email in self.email_to.split():
			if email:
				frappe.utils.validate_email_add(email, True)
				valid.append(email)

		self.email_to = '\n'.join(valid)

	def validate_report_count(self):
		'''check that there are only 3 enabled reports per user'''
		count = frappe.db.sql('select count(*) from `tabAuto Email Report` where user=%s and enabled=1', self.user)[0][0]
		if count > max_reports_per_user:
			frappe.throw(_('Only {0} emailed reports are allowed per user').format(max_reports_per_user))

	def get_report_content(self):
		'''Returns file in for the report in given format'''
		report = frappe.get_doc('Report', self.report)
		raw = report.get_data(limit=500, user = self.user, filters = self.filters)

		if self.format == 'HTML':
			return self.get_html_table(raw)

		elif self.format == 'XLS':
			return get_xls(raw)

		elif self.format == 'CSV':
			return to_csv(raw)

		else:
			frappe.throw(_('Invalid Output Format'))

	def get_html_table(self, data):
		return frappe.render_template('frappe/templates/includes/print_table.html', {
			'headings': data[0],
			'data': data[1:]
		})

	def get_file_name(self):
		return "{0}.{1}".format(self.report.replace(" ", "-").replace("/", "-"), self.format.lower())

	def send(self):
		data = self.get_report_content()
		attachments = None
		message = '<p>{0}</p>'.format(_('{0} generated on {1}')\
				.format(frappe.bold(self.name),
					frappe.utils.format_datetime(frappe.utils.now_datetime())))

		if self.description:
			message += '<hr>' + self.description

		if self.format=='HTML':
			message += '<hr>' + data
		else:
			attachments = [{
				'fname': self.get_file_name(),
				'fcontent': data
			}]

		message += '<hr><p style="font-size: 10px;"> Edit Auto Email Report Settings: {0}</p>'.format(frappe.utils.get_link_to_form('Auto Email Report', self.name))

		frappe.sendmail(
			recipients = self.email_to.split(),
			subject = self.name,
			message = message,
			attachments = attachments
		)

@frappe.whitelist()
def download(name):
	'''Download report locally'''
	auto_email_report = frappe.get_doc('Auto Email Report', name)
	auto_email_report.check_permission()
	data = auto_email_report.get_report_content()

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
	now = frappe.utils.now_datetime()
	for report in frappe.get_all('Auto Email Report',
		{'enabled': 1, 'frequency': ('in', ('Daily', 'Weekly'))}):
		auto_email_report = frappe.get_doc('Auto Email Report', report.name)

		# if not correct weekday, skip
		if auto_email_report.frequency=='Weekly':
			if now.weekday()!={'Monday':0,'Tuesday':1,'Wednesday':2,
				'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}[auto_email_report.weekday]:
				continue

		auto_email_report.send()


def send_monthly():
	'''Check reports to be sent monthly'''
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': 'Monthly'}):
		frappe.get_doc('Auto Email Report', report.name).send()
