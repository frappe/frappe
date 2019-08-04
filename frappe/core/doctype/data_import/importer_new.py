# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import io
import csv
import frappe
from datetime import datetime
from frappe import _
from frappe.utils import cint, flt, DATE_FORMAT, DATETIME_FORMAT
from frappe.utils.csvutils import read_csv_content
from frappe.exceptions import ValidationError, MandatoryError

# set user lang
# set flags: frappe.flags.in_import = True

# during import
	# check empty row
	# validate naming

class Importer:

	def __init__(self, doctype, file_path=None, content=None, options=None):
		self.doctype = doctype
		self.header_row = None
		self.data = None
		self.skipped_rows = []
		self._guessed_date_formats = {}
		self.meta = frappe.get_meta(doctype)

		if file_path:
			self.read_file(file_path)
		elif content:
			self.read_content(content)


	def read_file(self, file_path):
		extn = file_path.split('.')[1]

		file_content = None
		with io.open(file_path, mode='rb') as f:
			file_content = f.read()

		if extn == 'csv':
			data = read_csv_content(file_content)
			self.header_row = data[0]
			self.data = data[1:]


	def read_content(self, content):
		data = read_csv_content(content)
		self.header_row = data[0]
		self.data = data[1:]


	def parse_data_for_import(self, row, index):
		INVALID_VALUES = ['', None]

		if all(v in INVALID_VALUES for v in row):
			# empty row
			self.skipped_rows.append([index, 'Empty Row'])
			return

		doc = {}

		for i, field in enumerate(self.header_row):
			if not self.meta.has_field(field):
				continue

			df = self.meta.get_field(field)
			value = row[i]

			if value in INVALID_VALUES:
				if df.reqd:
					raise MandatoryError(_('Row {0}: {1} is a mandatory field').format(i, frappe.bold(df.label)))
				else:
					value = None

			# convert boolean values to 0 or 1
			if df.fieldtype == 'Check' and value.lower().strip() in ['t', 'f', 'true', 'false']:
				value = value.lower().strip()
				value = 1 if value in ['t', 'true'] else 0

			if df.fieldtype in ['Int', 'Check']:
				value = cint(value)
			elif df.fieldtype in ['Float', 'Percent', 'Currency']:
				value = flt(value)
			elif df.fieldtype in ['Date', 'Datetime']:
				value = self.parse_date_format(value, df)

			doc[df.fieldname] = value

		return frappe._dict(doc)


	def parse_date_format(self, value, df):
		date_format = self.guess_date_format_for_column(df.fieldname)
		return datetime.strptime(value, date_format)


	def guess_date_format_for_column(self, fieldname):
		''' Guesses date format for a column by parsing the first 10 values in the column,
		getting the date format and then returning the one which has the maximum frequency
		'''
		PARSE_ROW_COUNT = 10

		if not self._guessed_date_formats.get(fieldname):
			column_index = -1

			for i, field in enumerate(self.header_row):
				if self.meta.has_field(field) and field == fieldname:
					column_index = i
					break

			if column_index == -1:
				self._guessed_date_formats[fieldname] = None

			column_values = map(lambda x: x[column_index], self.data[:PARSE_ROW_COUNT])
			column_values = filter(lambda x: bool(x), column_values)
			date_formats = list(map(lambda x: guess_date_format(x), column_values))
			max_occurred_date_format = max(set(date_formats), key=date_formats.count)

			self._guessed_date_formats[fieldname] = max_occurred_date_format

		return self._guessed_date_formats[fieldname]


	def import_data(self):
		print('Importing {0} rows...'.format(len(self.data)))

		for i, row in enumerate(self.data):
			doc = self.parse_data_for_import(row, i)

			if doc:
				break



DATE_FORMATS = [
	r'%Y-%m-%d',
	r'%d-%m-%Y',
	r'%m-%d-%Y',

	r'%Y/%m/%d',
	r'%d/%m/%Y',
	r'%m/%d/%Y',

	r'%m/%d/%y',
	r'%d/%m/%y',

	r'%Y.%m.%d',
	r'%d.%m.%Y',
	r'%m.%d.%Y',
]

TIME_FORMATS = [
	r'%H:%M:%S.%f',
	r'%H:%M:%S',
	r'%H:%M',

	r'%I:%M:%S.%f %p',
	r'%I:%M:%S %p',
	r'%I:%M %p',
]

def guess_date_format(date_string):
	date_string = date_string.strip()

	_date = None
	_time = None

	if ' ' in date_string:
		_date, _time = date_string.split(' ', 1)
	else:
		_date = date_string

	date_format = None
	time_format = None

	for f in DATE_FORMATS:
		try:
			parsed_date = datetime.strptime(_date, f)
			date_format = f
			break
		except ValueError:
			pass

	if _time:
		for f in TIME_FORMATS:
			try:
				parsed_time = datetime.strptime(_time, f)
				time_format = f
				break
			except ValueError:
				pass

	full_format = date_format
	if time_format:
		full_format += ' ' + time_format
	return full_format


def import_data(doctype, file_path):
	i = Importer(doctype, file_path)
	i.import_data()
