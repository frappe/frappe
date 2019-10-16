from __future__ import unicode_literals

import calendar
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (format_time, get_link_to_form, get_url_to_report,
	global_date_format, now, now_datetime, validate_email_address, today, add_to_date)
from frappe.utils.csvutils import to_csv
from frappe.utils.xlsxutils import make_xlsx

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

def get_report_content(report_name, filters, format, no_of_rows, description=None, user=None, data_modified_till=None, from_date_field=None, to_date_field=None, dynamic_date_period=None, additional_params={}):
	def __dynamic_date_filters_set(dynamic_date_period, from_date_field, to_date_field):
		return dynamic_date_period and from_date_field and to_date_field

	def __prepare_dynamic_filters(filters, dynamic_date_period, from_date_field, to_date_field):
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

	report = frappe.get_doc('Report', report_name)
	report_type = report.report_type
	
	if report_type=='Report Builder' and data_modified_till:
		filters['modified'] = ('>', now_datetime() - timedelta(hours=data_modified_till))

	if report_type != 'Report Builder' and __dynamic_date_filters_set(dynamic_date_period, from_date_field, to_date_field):
		__prepare_dynamic_filters(filters, dynamic_date_period, from_date_field, to_date_field)

	columns, data = report.get_data(limit=no_of_rows or 100, user = user, filters = filters, as_dict=True)

	# add serial numbers
	columns.insert(0, frappe._dict(fieldname='idx', label='', width='30px'))
	for i in range(len(data)):
		data[i]['idx'] = i+1

	if len(data)==0 and self.send_if_data:
		return None

	if format == 'HTML':
		columns, data = make_links(columns, data)
		return get_html_table(report_name=report_name, report_type=report_type, description=description, columns=columns, data=data, additional_params = additional_params)
		
	elif format == 'XLSX':
		spreadsheet_data = get_spreadsheet_data(columns, data)
		xlsx_file = make_xlsx(spreadsheet_data, "Auto Email Report")
		return xlsx_file.getvalue()

	elif format == 'CSV':
		spreadsheet_data = get_spreadsheet_data(columns, data)
		return to_csv(spreadsheet_data)

	else:
		frappe.throw(_('Invalid Output Format'))


def get_html_table(report_name, report_type, title=None, description=None, columns=None, data=None, additional_params = {}):
	date_time = global_date_format(now()) + ' ' + format_time(now())
	report_doctype = frappe.db.get_value('Report', report_name, 'ref_doctype')
	
	template_context =  {
		'title': report_name,
		'description': description,
		'date_time': date_time,
		'columns': columns,
		'data': data,
		'report_url': get_url_to_report(report_name, report_type, report_doctype),
		'report_name': report_name
	}
	template_context.update(additional_params)
	return frappe.render_template('frappe/templates/emails/auto_email_report.html',template_context)

def get_spreadsheet_data(columns, data):
	out = [[_(df.label) for df in columns], ]
	for row in data:
		new_row = []
		out.append(new_row)
		for df in columns:
			if df.fieldname not in row: continue
			new_row.append(frappe.format(row[df.fieldname], df, row))

	return out

