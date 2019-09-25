# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import io
import csv
import json
import timeit
import frappe
from datetime import datetime
from frappe import _
from frappe.core.doctype.docfield.docfield import DocField
from frappe.utils import cint, flt, DATE_FORMAT, DATETIME_FORMAT
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import (
	read_xlsx_file_from_attached_file,
	read_xls_file_from_attached_file,
)
from frappe.exceptions import ValidationError, MandatoryError
from frappe.model import display_fieldtypes, no_value_fields, table_fields

INVALID_VALUES = ["", None]
MAX_ROWS_IN_PREVIEW = 500


class Importer:
	def __init__(self, doctype, data_import=None, file_path=None, content=None):
		self.doctype = doctype
		self.template_options = frappe._dict(
			{"remap_column": {}, "skip_import": [], "edited_rows": []}
		)

		if data_import:
			self.data_import = data_import
			if self.data_import.template_options:
				template_options = frappe.parse_json(self.data_import.template_options)
				self.template_options.update(template_options)
		else:
			self.data_import = None

		self.header_row = None
		self.data = None
		# used to store date formats guessed from data rows per column
		self._guessed_date_formats = {}
		self.last_eta = 0
		self.meta = frappe.get_meta(doctype)
		self.prepare_content(file_path, content)

	def prepare_content(self, file_path, content):
		if self.data_import:
			file_doc = frappe.get_doc("File", {"file_url": self.data_import.import_file})
			content = file_doc.get_content()
			extension = file_doc.file_name.split(".")[1]

		if file_path:
			self.read_file(file_path)
		elif content:
			self.read_content(content, extension)

		self.validate_template_content()
		self.remove_empty_rows_and_columns()

	def read_file(self, file_path):
		extn = file_path.split(".")[1]

		file_content = None
		with io.open(file_path, mode="rb") as f:
			file_content = f.read()

		if extn == "csv":
			data = read_csv_content(file_content)
			self.header_row = data[0]
			self.data = data[1:]

	def read_content(self, content, extension):
		if extension == "csv":
			data = read_csv_content(content)
		elif extension == "xlsx":
			data = read_xlsx_file_from_attached_file(fcontent=content)
		elif extension == "xls":
			data = read_xls_file_from_attached_file(content)

		self.header_row = data[0]
		self.data = data[1:]

	def validate_template_content(self):
		column_count = len(self.header_row)
		if any([len(row) != column_count and len(row) != 0 for row in self.data]):
			frappe.throw(
				_("Number of columns does not match with data"), title=_("Invalid Template")
			)

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

	def get_data_for_import_preview(self):
		out = self.get_parsed_data_from_template()

		# prepare fields
		fields = []
		for df in out.fields:
			header_title = df.header_title
			skip_import = df.skip_import
			if isinstance(df, DocField):
				field = df.as_dict()
			else:
				field = df
			field.update({"header_title": header_title, "skip_import": skip_import})
			fields.append(field)
		out.fields = fields

		if len(out.data) > MAX_ROWS_IN_PREVIEW:
			out.data = []
			out.max_rows_exceeded = True
		return out

	def get_parsed_data_from_template(self):
		fields, fields_warnings = self.parse_fields_from_header_row()
		formats, formats_warnings = self.parse_formats_from_first_10_rows()
		fields, data = self.add_serial_no_column(fields, self.data)

		if self.template_options.edited_rows:
			data = self.template_options.edited_rows

		warnings = fields_warnings + formats_warnings

		return frappe._dict(
			header_row=self.header_row, fields=fields, data=data, warnings=warnings
		)

	def parse_fields_from_header_row(self):
		remap_column = self.template_options.remap_column
		skip_import = self.template_options.skip_import
		fields = []
		warnings = []

		df_by_labels_and_fieldnames = self.build_fields_dict_for_column_matching()

		for i, header_title in enumerate(self.header_row):
			header_row_index = str(i)
			column_number = str(i + 1)
			if remap_column.get(header_row_index):
				fieldname = remap_column.get(header_row_index)
				df = df_by_labels_and_fieldnames.get(fieldname)
				warnings.append(
					{
						"col": column_number,
						"message": _("Mapping column {0} to field {1}").format(
							frappe.bold(header_title or "<i>Untitled Column</i>"), frappe.bold(df.label)
						),
					}
				)
			else:
				df = df_by_labels_and_fieldnames.get(header_title)

			if not df:
				field = frappe._dict(header_title=header_title, skip_import=True)
			else:
				field = df
				field.header_title = header_title
				field.skip_import = False

			if i in skip_import:
				field.skip_import = True
				warnings.append(
					{
						"col": column_number,
						"message": _("Skipping column {0}").format(frappe.bold(header_title)),
					}
				)
			elif header_title and not df:
				warnings.append(
					{
						"col": column_number,
						"message": _("Cannot match column {0} with any field").format(
							frappe.bold(header_title)
						),
					}
				)
			elif not header_title and not df:
				warnings.append({"col": column_number, "message": _("Skipping Untitled Column")})
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
		out = {}

		table_doctypes = [df.options for df in self.meta.get_table_fields()]
		doctypes = table_doctypes + [self.doctype]
		for doctype in doctypes:
			# name field
			name_key = "ID" if self.doctype == doctype else "ID ({})".format(doctype)
			name_df = frappe._dict(
				{
					"fieldtype": "Data",
					"fieldname": "name",
					"label": "ID",
					"reqd": self.data_import.import_type == "Update Existing Records",
					"parent": doctype,
				}
			)
			out[name_key] = name_df
			out["name"] = name_df

			# other fields
			meta = frappe.get_meta(doctype)
			fields = self.get_standard_fields(doctype) + meta.fields
			for df in fields:
				fieldtype = df.fieldtype or "Data"
				parent = df.parent or self.doctype
				if fieldtype not in no_value_fields:
					# label as key
					label = (
						df.label if self.doctype == doctype else "{0} ({1})".format(df.label, parent)
					)
					out[label] = df
					# fieldname as key
					if self.doctype == doctype:
						out[df.fieldname] = df
					else:
						key = "{0}:{1}".format(doctype, df.fieldname)
						out[key] = df

		# if autoname is based on field
		# add an entry for "ID (Autoname Field)"
		autoname = self.meta.autoname
		if autoname and autoname.startswith("field:"):
			fieldname = autoname[len("field:") :]
			autoname_field = self.meta.get_field(fieldname)
			if autoname_field:
				out["ID ({})".format(autoname_field.label)] = autoname_field
				# ID field should also map to the autoname field
				out["ID"] = autoname_field
				out["name"] = autoname_field

		return out

	def get_standard_fields(self, doctype):
		meta = frappe.get_meta(doctype)
		if meta.istable:
			standard_fields = [
				{"label": "Parent", "fieldname": "parent"},
				{"label": "Parent Type", "fieldname": "parenttype"},
				{"label": "Parent Field", "fieldname": "parentfield"},
				{"label": "Row Index", "fieldname": "idx"},
			]
		else:
			standard_fields = [
				{"label": "Owner", "fieldname": "owner"},
				{"label": "Document Status", "fieldname": "docstatus", "fieldtype": "Int"},
			]

		out = []
		for df in standard_fields:
			df = frappe._dict(df)
			df.parent = doctype
			out.append(df)
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
			frappe._dict({"label": "Sr. No", "skip_import": True, "parent": None})
		] + fields

		data_with_serial_no = []
		for i, row in enumerate(data):
			data_with_serial_no.append([self.row_index_map[i] + 1] + row)

		return fields_with_serial_no, data_with_serial_no

	def parse_value(self, value, df):
		# convert boolean values to 0 or 1
		if df.fieldtype == "Check" and value.lower().strip() in ["t", "f", "true", "false"]:
			value = value.lower().strip()
			value = 1 if value in ["t", "true"] else 0

		if df.fieldtype in ["Int", "Check"]:
			value = cint(value)
		elif df.fieldtype in ["Float", "Percent", "Currency"]:
			value = flt(value)
		elif df.fieldtype in ["Date", "Datetime"]:
			value = self.parse_date_format(value, df)

		return value

	def parse_date_format(self, value, df):
		date_format = self.guess_date_format_for_column(df.fieldname)
		if date_format:
			return datetime.strptime(value, date_format)
		return value

	def guess_date_format_for_column(self, fieldname):
		""" Guesses date format for a column by parsing the first 10 values in the column,
		getting the date format and then returning the one which has the maximum frequency
		"""
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
			if not date_formats:
				return
			max_occurred_date_format = max(set(date_formats), key=date_formats.count)
			self._guessed_date_formats[fieldname] = max_occurred_date_format

		return self._guessed_date_formats[fieldname]

	def import_data(self):
		# set user lang for translations
		frappe.cache().hdel("lang", frappe.session.user)
		frappe.set_user_lang(frappe.session.user)

		# set flag
		frappe.flags.in_import = True

		out = self.get_parsed_data_from_template()
		fields = out["fields"]
		data = out["data"]
		warnings = []

		# prepare a map for missing link field values
		self.prepare_missing_link_field_values(fields, data)

		# parse import data
		payloads = self.get_payloads_for_import(fields, data)

		# collect warnings
		for payload in payloads:
			warnings += payload.warnings

		if warnings:
			self.data_import.db_set("template_warnings", json.dumps(warnings))
			frappe.publish_realtime("data_import_refresh")
			return
		else:
			self.data_import.db_set("template_warnings", "")

		# setup import log
		if self.data_import.import_log:
			import_log = frappe.parse_json(self.data_import.import_log)
		else:
			import_log = []

		# remove previous failures from import log
		import_log = [l for l in import_log if l.get("success") == True]

		# get successfully imported rows
		imported_rows = []
		for log in import_log:
			log = frappe._dict(log)
			if log.success:
				imported_rows += log.row_indexes

		# start import
		print("Importing {0} rows...".format(len(data)))
		# mark savepoint
		frappe.db.sql("SAVEPOINT import")

		total_payload_count = len(payloads)
		batch_size = frappe.conf.data_import_batch_size or 1000

		for batch_index, batched_payloads in enumerate(
			frappe.utils.create_batch(payloads, batch_size)
		):
			for i, payload in enumerate(batched_payloads):
				doc = payload.doc
				row_indexes = [row[0] for row in payload.rows]
				current_index = (i + 1) + (batch_index * batch_size)

				if set(row_indexes).intersection(set(imported_rows)):
					print("Skipping imported rows", row_indexes)
					frappe.publish_realtime(
						"data_import_progress",
						{"current": current_index, "total": total_payload_count, "skipping": True},
					)
					continue

				try:
					print("Importing", doc)
					start = timeit.default_timer()
					doc = self.process_doc(doc)
					processing_time = timeit.default_timer() - start
					eta = self.get_eta(current_index, total_payload_count, processing_time)
					frappe.publish_realtime(
						"data_import_progress",
						{
							"current": current_index,
							"total": total_payload_count,
							"docname": doc.name,
							"success": True,
							"row_indexes": row_indexes,
							"eta": eta,
						},
					)
					import_log.append(
						frappe._dict(success=True, docname=doc.name, row_indexes=row_indexes)
					)

				except Exception as e:
					import_log.append(
						frappe._dict(
							success=False,
							exception=frappe.get_traceback(),
							messages=frappe.local.message_log,
							row_indexes=row_indexes,
						)
					)
					frappe.clear_messages()

		# rollback to savepoint if something went wrong
		# frappe.db.sql('ROLLBACK TO SAVEPOINT import')

		# release savepoint if everything is ok
		frappe.db.sql("RELEASE SAVEPOINT import")

		# set status
		failures = [l for l in import_log if l.get("success") == False]
		if len(failures) == total_payload_count:
			status = "Pending"
		elif len(failures) > 0:
			status = "Partial Success"
		else:
			status = "Success"

		self.data_import.db_set("status", status)
		self.data_import.db_set("import_log", json.dumps(import_log))

		frappe.flags.in_import = False
		frappe.publish_realtime("data_import_refresh")

	def get_payloads_for_import(self, fields, data):
		payloads = []
		while data:
			doc, rows, data, warnings = self.parse_next_row_for_import(fields, data)
			payloads.append(frappe._dict(doc=doc, rows=rows, warnings=warnings))
		return payloads

	def parse_next_row_for_import(self, fields, data):
		"""
		Parses rows that make up a doc. A doc maybe built from a single row or multiple rows.
		Returns the doc, rows, data without the rows and warnings.
		"""
		doc = {}
		warnings = []
		mandatory_fields = []
		doctypes = set([df.parent for df in fields if df.parent])

		# first row is included by default
		first_row = data[0]
		rows = [first_row]

		# if there are child doctypes, find the subsequent rows
		if len(doctypes) > 1:
			# subsequent rows either dont have any parent value set
			# or have the same value as the parent
			# we include a row if either of conditions match
			parent_column_index = self.get_first_parent_column_index(fields)
			parent_value = first_row[parent_column_index]
			data_without_first_row = data[1:]
			for d in data_without_first_row:
				value = d[parent_column_index]
				# if value is blank then it's a child row
				# if value is same as parent value it's a child row
				# if value is different than the parent value, it's the next doc
				if value not in INVALID_VALUES and value != parent_value:
					break
				rows.append(d)

		def get_column_indexes(doctype):
			return [i for i, df in enumerate(fields) if df.parent == doctype]

		def validate_value(value, df):
			validate_warnings = []

			if df.fieldtype == "Select" and value not in df.get_select_options():
				options_string = ", ".join([frappe.bold(d) for d in df.get_select_options()])
				msg = _("Value must be one of {0}").format(options_string)
				validate_warnings.append(
					{"row": row_number, "field": df.as_dict(convert_dates_to_str=True), "message": msg}
				)

			elif df.fieldtype == "Link":
				missing_link_values = self.get_missing_link_field_values(df.options)
				if value in missing_link_values:
					msg = _("Value {0} missing for Document Type {1}").format(
						frappe.bold(value), frappe.bold(df.options)
					)
					validate_warnings.append(
						{
							"row": row_number,
							"field": df.as_dict(convert_dates_to_str=True),
							"message": msg,
						}
					)

			if validate_warnings:
				warnings.extend(validate_warnings)
				return False

			return True

		def parse_doc(doctype, docfields, values, row_number):
			doc = {}
			for index, (df, value) in enumerate(zip(docfields, values)):
				if df.get("skip_import", False):
					continue

				if value in INVALID_VALUES:
					value = None

				if validate_value(value, df):
					doc[df.fieldname] = self.parse_value(value, df)

			check_mandatory_fields(doctype, doc, row_number)

			return doc

		def check_mandatory_fields(doctype, doc, row_number):
			meta = frappe.get_meta(doctype)
			fields = [df for df in meta.fields if df.reqd and doc.get(df.fieldname) in INVALID_VALUES]

			if not fields:
				return

			if len(fields) == 1:
				warnings.append(
					{
						"row": row_number,
						"message": _("{0} is a mandatory field").format(fields[0].label),
					}
				)
			else:
				fields_string = ", ".join([df.label for df in fields])
				warnings.append(
					{
						"row": row_number,
						"message": _("{0} are mandatory fields").format(fields_string),
					}
				)


		parsed_docs = {}
		for row_index, row in enumerate(rows):
			for doctype in doctypes:
				if doctype == self.doctype and parsed_docs.get(doctype):
					# if parent doc is already parsed from the first row
					# then skip
					continue

				row_number = row[0]
				column_indexes = get_column_indexes(doctype)
				values = [row[i] for i in column_indexes]

				if all(v in INVALID_VALUES for v in values):
					# skip values if all of them are empty
					continue

				docfields = [fields[i] for i in column_indexes]
				doc = parse_doc(doctype, docfields, values, row_number)
				parsed_docs[doctype] = parsed_docs.get(doctype, [])
				parsed_docs[doctype].append(doc)

		for doctype, docs in parsed_docs.items():
			if doctype == self.doctype:
				doc = docs[0]
			else:
				table_dfs = self.meta.get(
					"fields", {"options": doctype, "fieldtype": ["in", table_fields]}
				)
				if table_dfs:
					table_field = table_dfs[0]
					doc[table_field.fieldname] = docs

		return doc, rows, data[len(rows) :], warnings

	def get_first_parent_column_index(self, fields):
		"""
		Returns the first column's index which must be one of the parent columns
		"""
		# find a parent column
		parent_column_index = -1
		for i, df in enumerate(fields):
			if not df.get("skip_import", False) and df.parent == self.doctype:
				parent_column_index = i
				break
		return parent_column_index

	def process_doc(self, doc):
		import_type = self.data_import.import_type

		if import_type == "Insert New Records":
			return self.insert_record(doc)
		elif import_type == "Update Existing Records":
			return self.update_record(doc)

	def insert_record(self, doc):
		# name shouldn't be set when inserting a new record
		doc.update({"doctype": self.doctype, "name": None})
		new_doc = frappe.get_doc(doc)
		new_doc.insert()
		if self.meta.is_submittable and self.data_import.submit_after_import:
			new_doc.submit()
		return new_doc

	def update_record(self, doc):
		id_fieldname = self.get_id_fieldname()
		id_value = doc[id_fieldname]
		existing_doc = frappe.get_doc(self.doctype, {id_fieldname: id_value})
		existing_doc.flags.via_data_import = self.data_import.name
		existing_doc.update(doc)
		existing_doc.save()
		return existing_doc

	def export_errored_rows(self):
		from frappe.utils.csvutils import build_csv_response

		if not self.data_import:
			return

		import_log = frappe.parse_json(self.data_import.import_log or "[]")
		failures = [l for l in import_log if l.get("success") == False]
		row_indexes = []
		for f in failures:
			row_indexes.extend(f.get("row_indexes", []))

		# de duplicate
		row_indexes = list(set(row_indexes))
		row_indexes.sort()

		out = self.get_parsed_data_from_template()
		header_row = out["header_row"]
		data = out["data"]

		rows = [header_row]
		rows += [row[1:] for row in data if row[0] in row_indexes]

		build_csv_response(rows, self.doctype)

	def get_missing_link_field_values(self, doctype):
		return self.missing_link_values.get(doctype, [])

	def prepare_missing_link_field_values(self, fields, data):
		link_column_indexes = [i for i, df in enumerate(fields) if df.fieldtype == "Link"]

		def has_one_mandatory_field(doctype):
			meta = frappe.get_meta(doctype)
			# get mandatory fields with default not set
			mandatory_fields = [df for df in meta.fields if df.reqd and not df.default]
			mandatory_fields_count = len(mandatory_fields)
			if meta.autoname and meta.autoname.lower() == "prompt":
				mandatory_fields_count += 1
			return mandatory_fields_count == 1

		self.missing_link_values = {}
		for index in link_column_indexes:
			df = fields[index]
			column_values = [row[index] for row in data]
			values = set([v for v in column_values if v not in INVALID_VALUES])
			doctype = df.options

			missing_values = [value for value in values if not frappe.db.exists(doctype, value)]
			self.missing_link_values[doctype] = missing_values

	def get_id_fieldname(self):
		autoname = self.meta.autoname
		if autoname and autoname.startswith("field:"):
			fieldname = autoname[len("field:") :]
			autoname_field = self.meta.get_field(fieldname)
			if autoname_field:
				return autoname_field.fieldname
		return "name"

	def get_eta(self, current, total, processing_time):
		remaining = total - current
		eta = processing_time * remaining
		if not self.last_eta or eta < self.last_eta:
			self.last_eta = eta
		return self.last_eta


DATE_FORMATS = [
	r"%d-%m-%Y",
	r"%m-%d-%Y",
	r"%Y-%m-%d",
	r"%d-%m-%y",
	r"%m-%d-%y",
	r"%y-%m-%d",
	r"%d/%m/%Y",
	r"%m/%d/%Y",
	r"%Y/%m/%d",
	r"%d/%m/%y",
	r"%m/%d/%y",
	r"%y/%m/%d",
	r"%d.%m.%Y",
	r"%m.%d.%Y",
	r"%Y.%m.%d",
	r"%d.%m.%y",
	r"%m.%d.%y",
	r"%y.%m.%d",
]

TIME_FORMATS = [
	r"%H:%M:%S.%f",
	r"%H:%M:%S",
	r"%H:%M",
	r"%I:%M:%S.%f %p",
	r"%I:%M:%S %p",
	r"%I:%M %p",
]


def guess_date_format(date_string):
	date_string = date_string.strip()

	_date = None
	_time = None

	if " " in date_string:
		_date, _time = date_string.split(" ", 1)
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
		full_format += " " + time_format
	return full_format


def import_data(doctype, file_path):
	i = Importer(doctype, file_path)
	i.import_data()
