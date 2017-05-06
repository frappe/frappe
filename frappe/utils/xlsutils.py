from __future__ import unicode_literals

import frappe, xlwt, StringIO, datetime
from frappe import _

def get_xls(columns, data):
	'''Convert data to xls'''
	stream = StringIO.StringIO()
	workbook = xlwt.Workbook()
	sheet = workbook.add_sheet(_("Sheet 1"))

	# formats
	dateformat = xlwt.easyxf(num_format_str=
		(frappe.defaults.get_global_default("date_format") or "yyyy-mm-dd"))
	bold = xlwt.easyxf('font: bold 1')

	# header
	for i, col in enumerate(columns):
		sheet.write(0, i, col.label, bold)

	for i, row in enumerate(data):
		for j, df in enumerate(columns):
			f = None

			val = row[columns[j].fieldname]
			if isinstance(val, (datetime.datetime, datetime.date)):
				f = dateformat

			if f:
				sheet.write(i+1, j, val, f)
			else:
				sheet.write(i+1, j, frappe.format(val, df, row))

	workbook.save(stream)
	stream.seek(0)
	return stream.read()
