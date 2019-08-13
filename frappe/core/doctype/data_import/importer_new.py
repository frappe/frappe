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
from frappe.model import display_fieldtypes, no_value_fields, table_fields

# set user lang
# set flags: frappe.flags.in_import = True

# during import
	# check empty row
	# validate naming

INVALID_VALUES = ['', None]

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

		self.remove_empty_rows_and_columns()

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


	def remove_empty_rows_and_columns(self):
		self.row_index_map = []
		removed_rows = []
		removed_columns = []

		# remove empty rows
		data = []
		for i, row in enumerate(self.data):
			if all(v in INVALID_VALUES for v in row):
				# empty row
				removed_rows.append(i)
			else:
				data.append(row)
				self.row_index_map.append(i)

		# remove empty columns
		# a column with a header and no data is a valid column
		# a column with no header and no data will be removed
		header_row = []
		for i, column in enumerate(self.header_row):
			column_values = [row[i] for row in data]
			values = [column] + column_values
			if all(v in INVALID_VALUES for v in values):
				# empty column
				removed_columns.append(i)
			else:
				header_row.append(column)

		data_without_empty_columns = []
		# remove empty columns from data
		for i, row in enumerate(data):
			new_row = [v for j, v in enumerate(row) if j not in removed_columns]
			data_without_empty_columns.append(new_row)

		self.data = data_without_empty_columns
		self.header_row = header_row


	def get_data_for_import_preview(self, import_options=None):
		import_options = import_options or frappe._dict()
		remap_columns = import_options.remap_column
		skip_import = import_options.skip_import

		fields, fields_warnings = self.parse_fields_from_header_row(remap_columns, skip_import)
		formats, formats_warnings = self.parse_formats_from_first_10_rows()
		fields, data = self.add_serial_no_column(fields, self.data)

		warnings = fields_warnings + formats_warnings

		return dict(
			header_row=self.header_row,
			fields=fields,
			data=data,
			warnings=warnings
		)


	def parse_fields_from_header_row(self, remap_columns, skip_import):
		remap_columns = remap_columns or frappe._dict()
		skip_import = skip_import or []
		fields = []
		warnings = []

		df_by_labels_and_fieldnames = self.build_fields_dict_for_column_matching()

		for i, value in enumerate(self.header_row):
			if remap_columns.get(value):
				column_name = value
				value = remap_columns.get(value)
				warnings.append(_('Column {0}: Mapping column {1} to field {2}').format(
					i, frappe.bold(column_name), frappe.bold(value)))

			field = df_by_labels_and_fieldnames.get(value)
			if not field or value in skip_import:
				field = {
					'label': value,
					'skip_import': True
				}
				if value and value not in skip_import:
					warnings.append(_('Column {0}: Cannot match column {1} with any field').format(i, frappe.bold(value)))
				elif value in skip_import:
					warnings.append(_('Column {0}: Skipping column {1}').format(i, frappe.bold(value)))
				else:
					warnings.append(_('Column {0}: Skipping untitled column').format(i))
			fields.append(field)

		return fields, warnings


	def build_fields_dict_for_column_matching(self):
		"""
		Build a dict with various keys to match with column headers and value as docfield
		The keys can be label or fieldname
		{
		 'Customer': df1,
		 'customer': df1,
		 'Due Date': df2,
		 'due_date': df2,
		 'Item Code (Sales Invoice Item)': df3,
		 'Sales Invoice Item:item_code': df3,
		}
		"""
		out = {
			'ID': frappe._dict({
				'fieldtype': 'Data',
				'fieldname': 'name',
				'label': 'ID',
				'reqd': 1,
				'parent': self.doctype
			})
		}

		doctypes = [self.doctype] + [df.options for df in self.meta.get_table_fields()]
		for doctype in doctypes:
			meta = frappe.get_meta(doctype)
			for df in meta.fields:
				if df.fieldtype not in no_value_fields:
					# label as key
					label = df.label if self.doctype == doctype else '{0} ({1})'.format(df.label, df.parent)
					out[label] = df
					# fieldname as key
					if self.doctype == doctype:
						out[df.fieldname] = df
					else:
						key = '{0}:{1}'.format(doctype, df.fieldname)
						out[key] = df

		# if autoname is based on field
		# add an entry for "ID (Autoname Field)"
		autoname = self.meta.autoname
		if autoname and autoname.startswith('field:'):
			fieldname = autoname[len('field:'):]
			autoname_field = self.meta.get_field(fieldname)
			if autoname_field:
				out['ID ({})'.format(autoname_field.label)] = autoname_field
				# ID field should also map to the autoname field
				out['ID'] = autoname_field

		return out


	def parse_formats_from_first_10_rows(self):
		"""
		Returns a list of column descriptors for columns that might need parsing.
		For e.g if it is a Date column return the Date format
		[
			[['Data']],
			[['Date', '%m/%d/%y']],
			[['Currency', '#,###.##']],
			...
		]
		"""
		formats = []
		return formats, []


	def add_serial_no_column(self, fields, data):
		fields_with_serial_no = [
			{
				'label': 'Sr. No',
				'skip_import': True
			}
		] + fields

		data_with_serial_no = []
		for i, row in enumerate(data):
			data_with_serial_no.append([self.row_index_map[i] + 1] + row)

		return fields_with_serial_no, data_with_serial_no


	def parse_data_for_import(self, row, index):

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
