# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.model.document import Document
from datetime import timedelta
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
		self.validate_report_format()

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
		if count > max_reports_per_user + (-1 if self.flags.in_insert else 0):
			frappe.throw(_('Only {0} emailed reports are allowed per user').format(max_reports_per_user))

	def validate_report_format(self):
		""" check if user has select correct report format """
		valid_report_formats = ["HTML", "XLS", "CSV"]
		if self.format not in valid_report_formats:
			frappe.throw(_("%s is not a valid report format. Report format should \
				one of the following %s"%(frappe.bold(self.format), frappe.bold(", ".join(valid_report_formats)))))

	def get_report_content(self):
		'''Returns file in for the report in given format'''
		report = frappe.get_doc('Report', self.report)

		if self.report_type=='Report Builder' and self.data_modified_till:
			self.filters = json.loads(self.filters) if self.filters else {}
			self.filters['modified'] = ('>', frappe.utils.now_datetime() - timedelta(hours=self.data_modified_till))

		columns, data = report.get_data(limit=self.no_of_rows or 100, user = self.user,
			filters = self.filters, as_dict=True)

		# add serial numbers
		columns.insert(0, frappe._dict(fieldname='idx', label='', width='30px'))
		for i in range(len(data)):
			data[i]['idx'] = i+1

		if len(data)==0 and self.send_if_data:
			return None

		if self.format == 'HTML':
			return self.get_html_table(columns, data)

		elif self.format == 'XLS':
			return get_xls(columns, data)

		elif self.format == 'CSV':
			return self.get_csv(columns, data)

		else:
			frappe.throw(_('Invalid Output Format'))

	def get_html_table(self, columns, data):
		return frappe.render_template('frappe/templates/includes/print_table.html', {
			'columns': columns,
			'data': data
		})

	def get_csv(self, columns, data):
		out = [[df.label for df in columns], ]
		for row in data:
			new_row = []
			out.append(new_row)
			for df in columns:
				new_row.append(frappe.format(row[df.fieldname], df, row))

		return to_csv(out)

	def get_file_name(self):
		return "{0}.{1}".format(self.report.replace(" ", "-").replace("/", "-"), self.format.lower())

	def send(self):
		if self.filter_meta and not self.filters:
			frappe.throw(_("Please set filters value in Report Filter table."))

		data = self.get_report_content()
		if not data:
			return

		attachments = None
		message = '<p>{0}</p>'.format(_('{0} generated on {1}')\
				.format(frappe.bold(self.name),
					frappe.utils.format_datetime(frappe.utils.now_datetime())))

		if self.description:
			message += '<hr style="margin: 15px 0px;">' + self.description

		if self.format=='HTML':
			message += '<hr>' + data
		else:
			attachments = [{
				'fname': self.get_file_name(),
				'fcontent': data
			}]

		report_doctype = frappe.db.get_value('Report', self.report, 'ref_doctype')
		report_footer = frappe.render_template(self.get_report_footer(),
			dict(report_url = frappe.utils.get_url_to_report(self.report, self.report_type, report_doctype),
			report_name = self.report,
			edit_report_settings = frappe.utils.get_link_to_form('Auto Email Report', self.name)))

		message += report_footer

		frappe.sendmail(
			recipients = self.email_to.split(),
			subject = self.name,
			message = message,
			attachments = attachments
		)

	def get_report_footer(self):
		return """<hr style="margin: 30px 0px 15px 0px;">
		<p style="font-size: 9px;">
			View report in your browser:
			<a href= {{report_url}} target="_blank">{{report_name}}</a><br><br>
			Edit Auto Email Report Settings: {{edit_report_settings}}
		</p>"""

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
	now = frappe.utils.now_datetime()
	for report in frappe.get_all('Auto Email Report',
		{'enabled': 1, 'frequency': ('in', ('Daily', 'Weekly'))}):
		auto_email_report = frappe.get_doc('Auto Email Report', report.name)

		# if not correct weekday, skip
		if auto_email_report.frequency=='Weekly':
			if now.weekday()!={'Monday':0,'Tuesday':1,'Wednesday':2,
				'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}[auto_email_report.day_of_week]:
				continue

		auto_email_report.send()


def send_monthly():
	'''Check reports to be sent monthly'''
	for report in frappe.get_all('Auto Email Report', {'enabled': 1, 'frequency': 'Monthly'}):
		frappe.get_doc('Auto Email Report', report.name).send()
