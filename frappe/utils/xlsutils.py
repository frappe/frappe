from __future__ import unicode_literals

import frappe, xlwt, StringIO, datetime
from frappe import _

def get_xls(data):
	'''Convert data to xls'''
	stream = StringIO.StringIO()
	workbook = xlwt.Workbook()
	sheet = workbook.add_sheet(_("Sheet 1"))

	# formats
	dateformat = xlwt.easyxf(num_format_str=
		(frappe.defaults.get_global_default("date_format") or "yyyy-mm-dd"))
	bold = xlwt.easyxf('font: bold 1')

	for i, row in enumerate(data):
		for j, val in enumerate(row):
			f = None
			if isinstance(val, (datetime.datetime, datetime.date)):
				f = dateformat
			if i==0:
				f = bold

			if f:
				sheet.write(i, j, val, f)
			else:
				sheet.write(i, j, val)

	workbook.save(stream)
	stream.seek(0)
	return stream.read()
