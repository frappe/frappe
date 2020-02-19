# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import io
import os
import json
import timeit
import frappe
from datetime import datetime
from frappe import _
from frappe.utils import cint, flt, update_progress_bar, cstr
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import (
	read_xlsx_file_from_attached_file,
	read_xls_file_from_attached_file,
)
from frappe.model import no_value_fields, table_fields

INVALID_VALUES = ["", None]
MAX_ROWS_IN_PREVIEW = 10
INSERT = "Insert New Records"
UPDATE = "Update Existing Records"

# pylint: disable=R0201
class Importer:
	def __init__(
		self, doctype, data_import=None, file_path=None, content=None, console=False
	):
		self.doctype = doctype
		self.template_options = frappe._dict({"remap_column": {}})
		self.console = console

		if data_import:
			self.data_import = data_import
			if self.data_import.template_options:
				template_options = frappe.parse_json(self.data_import.template_options)
				self.template_options.update(template_options)
			self.import_type = self.data_import.import_type
		else:
			self.data_import = None

		self.import_type = self.import_type or INSERT

		self.header_row = None
		self.data = None
		# used to store date formats guessed from data rows per column
		self._guessed_date_formats = {}
		# used to store eta during import
		self.last_eta = 0
		# used to collect warnings during template parsing
		# and show them to user
		self.warnings = []
		self.meta = frappe.get_meta(doctype)
		self.prepare_content(file_path, content)
		self.parse_data_from_template()

	def prepare_content(self, file_path, content):
		extension = None
		if self.data_import and self.data_import.import_file:
			file_doc = frappe.get_doc("File", {"file_url": self.data_import.import_file})
			parts = file_doc.get_extension()
			extension = parts[1]
			content = file_doc.get_content()
			extension = extension.lstrip(".")

		if file_path:
			content, extension = self.read_file(file_path)

		if not extension:
			extension = "csv"

		if content:
			self.read_content(content, extension)

		self.validate_template_content()
		self.remove_empty_rows_and_columns()

	def read_file(self, file_path):
		extn = file_path.split(".")[1]

		file_content = None
		with io.open(file_path, mode="rb") as f:
			file_content = f.read()

		return file_content, extn

	def read_content(self, content, extension):
		error_title = _("Template Error")
		if extension not in ("csv", "xlsx", "xls"):
			frappe.throw(
				_("Import template should be of type .csv, .xlsx or .xls"), title=error_title
			)

		if extension == "csv":
			data = read_csv_content(content)
		elif extension == "xlsx":
			data = read_xlsx_file_from_attached_file(fcontent=content)
		elif extension == "xls":
			data = read_xls_file_from_attached_file(content)

		if len(data) <= 1:
			frappe.throw(
				_("Import template should contain a Header and atleast one row."), title=error_title
			)

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
		out = frappe._dict()
		out.data = list(self.rows)
		out.columns = self.columns
		out.warnings = self.warnings
		total_number_of_rows = len(out.data)
		if total_number_of_rows > MAX_ROWS_IN_PREVIEW:
			out.data = out.data[:MAX_ROWS_IN_PREVIEW]
			out.max_rows_exceeded = True
			out.max_rows_in_preview = MAX_ROWS_IN_PREVIEW
			out.total_number_of_rows = total_number_of_rows
		return out

	def parse_data_from_template(self):
		columns = self.parse_columns_from_header_row()
		columns = self.detect_date_formats(columns)
		columns, data = self.add_serial_no_column(columns, self.data)

		self.columns = columns
		self.rows = data

	def parse_columns_from_header_row(self):
		remap_column = self.template_options.remap_column
		columns = []

		df_by_labels_and_fieldnames = self.build_fields_dict_for_column_matching()

		for i, header_title in enumerate(self.header_row):
			header_row_index = str(i)
			column_number = str(i + 1)
			skip_import = False
			fieldname = remap_column.get(header_row_index)

			if fieldname and fieldname != "Don't Import":
				df = df_by_labels_and_fieldnames.get(fieldname)
				self.warnings.append(
					{
						"col": column_number,
						"message": _("Mapping column {0} to field {1}").format(
							frappe.bold(header_title or "<i>Untitled Column</i>"), frappe.bold(df.label)
						),
						"type": "info",
					}
				)
			else:
				df = df_by_labels_and_fieldnames.get(header_title)

			if not df:
				skip_import = True
			else:
				skip_import = False

			if fieldname == "Don't Import":
				skip_import = True
				self.warnings.append(
					{
						"col": column_number,
						"message": _("Skipping column {0}").format(frappe.bold(header_title)),
						"type": "info",
					}
				)
			elif header_title and not df:
				self.warnings.append(
					{
						"col": column_number,
						"message": _("Cannot match column {0} with any field").format(
							frappe.bold(header_title)
						),
						"type": "info",
					}
				)
			elif not header_title and not df:
				self.warnings.append(
					{"col": column_number, "message": _("Skipping Untitled Column"), "type": "info"}
				)

			columns.append(
				frappe._dict(
					df=df,
					skip_import=skip_import,
					header_title=header_title,
					column_number=column_number,
					index=i,
				)
			)

		return columns

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
					"reqd": self.import_type == UPDATE,
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
		autoname_field = self.get_autoname_field(self.doctype)
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

	def detect_date_formats(self, columns):
		for col in columns:
			if col.df and col.df.fieldtype in ['Date', 'Time', 'Datetime']:
				col.date_format = self.guess_date_format_for_column(col, columns)
		return columns

	def add_serial_no_column(self, columns, data):
		columns_with_serial_no = [
			frappe._dict({"header_title": "Sr. No", "skip_import": True})
		] + columns

		# update index for each column
		for i, col in enumerate(columns_with_serial_no):
			col.index = i

		data_with_serial_no = []
		for i, row in enumerate(data):
			data_with_serial_no.append([self.row_index_map[i] + 1] + row)

		return columns_with_serial_no, data_with_serial_no

	def parse_value(self, value, df):
		value = cstr(value)

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
		date_format = self.get_date_format_for_df(df)
		if date_format:
			try:
				return datetime.strptime(value, date_format)
			except:
				# ignore date values that dont match the format
				# import will break for these values later
				pass
		return value

	def get_date_format_for_df(self, df):
		return self._guessed_date_formats.get(df.parent + df.fieldname)

	def guess_date_format_for_column(self, column, columns):
		""" Guesses date format for a column by parsing the first 10 values in the column,
		getting the date format and then returning the one which has the maximum frequency
		"""
		PARSE_ROW_COUNT = 10

		df = column.df
		key = df.parent + df.fieldname

		if not self._guessed_date_formats.get(key):
			matches = [col for col in columns if col.df == df]
			if not matches:
				self._guessed_date_formats[key] = None
				return

			column = matches[0]
			column_index = column.index

			date_values = [
				row[column_index] for row in self.data[:PARSE_ROW_COUNT] if row[column_index]
			]
			date_formats = [guess_date_format(d) for d in date_values]
			if not date_formats:
				return
			max_occurred_date_format = max(set(date_formats), key=date_formats.count)
			self._guessed_date_formats[key] = max_occurred_date_format

		return self._guessed_date_formats[key]

	def import_data(self):
		# set user lang for translations
		frappe.cache().hdel("lang", frappe.session.user)
		frappe.set_user_lang(frappe.session.user)

		if not self.console:
			self.data_import.db_set("template_warnings", "")

		# set flags
		frappe.flags.in_import = True
		frappe.flags.mute_emails = self.data_import.mute_emails

		# prepare a map for missing link field values
		self.prepare_missing_link_field_values()

		# parse docs from rows
		payloads = self.get_payloads_for_import()

		# dont import if there are non-ignorable warnings
		warnings = [w for w in self.warnings if w.get("type") != "info"]
		if warnings:
			if self.console:
				self.print_grouped_warnings(warnings)
			else:
				self.data_import.db_set("template_warnings", json.dumps(warnings))
				frappe.publish_realtime(
					"data_import_refresh", {"data_import": self.data_import.name}
				)
			return

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
					if total_payload_count > 5:
						frappe.publish_realtime(
							"data_import_progress",
							{
								"current": current_index,
								"total": total_payload_count,
								"skipping": True,
								"data_import": self.data_import.name,
							},
						)
					continue

				try:
					start = timeit.default_timer()
					doc = self.process_doc(doc)
					processing_time = timeit.default_timer() - start
					eta = self.get_eta(current_index, total_payload_count, processing_time)

					if total_payload_count > 5:
						frappe.publish_realtime(
							"data_import_progress",
							{
								"current": current_index,
								"total": total_payload_count,
								"docname": doc.name,
								"data_import": self.data_import.name,
								"success": True,
								"row_indexes": row_indexes,
								"eta": eta,
							},
						)
					if self.console:
						update_progress_bar(
							"Importing {0} records".format(total_payload_count),
							current_index,
							total_payload_count,
						)
					import_log.append(
						frappe._dict(success=True, docname=doc.name, row_indexes=row_indexes)
					)
					# commit after every successful import
					frappe.db.commit()

				except Exception:
					import_log.append(
						frappe._dict(
							success=False,
							exception=frappe.get_traceback(),
							messages=frappe.local.message_log,
							row_indexes=row_indexes,
						)
					)
					frappe.clear_messages()
					# rollback if exception
					frappe.db.rollback()

		# set status
		failures = [l for l in import_log if l.get("success") == False]
		if len(failures) == total_payload_count:
			status = "Pending"
		elif len(failures) > 0:
			status = "Partial Success"
		else:
			status = "Success"

		if self.console:
			self.print_import_log(import_log)
		else:
			self.data_import.db_set("status", status)
			self.data_import.db_set("import_log", json.dumps(import_log))

		frappe.flags.in_import = False
		frappe.flags.mute_emails = False
		frappe.publish_realtime("data_import_refresh", {"data_import": self.data_import.name})

		return import_log

	def get_payloads_for_import(self):
		payloads = []
		# make a copy
		data = list(self.rows)
		while data:
			doc, rows, data = self.parse_next_row_for_import(data)
			payloads.append(frappe._dict(doc=doc, rows=rows))
		return payloads

	def parse_next_row_for_import(self, data):
		"""
		Parses rows that make up a doc. A doc maybe built from a single row or multiple rows.
		Returns the doc, rows, and data without the rows.
		"""
		doctypes = set([col.df.parent for col in self.columns if col.df and col.df.parent])

		# first row is included by default
		first_row = data[0]
		rows = [first_row]

		# if there are child doctypes, find the subsequent rows
		if len(doctypes) > 1:
			# subsequent rows either dont have any parent value set
			# or have the same value as the parent row
			# we include a row if either of conditions match
			parent_column_indexes = [
				col.index
				for col in self.columns
				if not col.skip_import and col.df and col.df.parent == self.doctype
			]
			parent_row_values = [first_row[i] for i in parent_column_indexes]

			data_without_first_row = data[1:]
			for row in data_without_first_row:
				row_values = [row[i] for i in parent_column_indexes]
				# if the row is blank, it's a child row doc
				if all([v in INVALID_VALUES for v in row_values]):
					rows.append(row)
					continue
				# if the row has same values as parent row, it's a child row doc
				if row_values == parent_row_values:
					rows.append(row)
					continue
				# if any of those conditions dont match, it's the next doc
				break

		def get_column_indexes(doctype):
			return [
				col.index
				for col in self.columns
				if not col.skip_import and col.df and col.df.parent == doctype
			]

		def validate_value(value, df):
			if df.fieldtype == "Select":
				select_options = df.get_select_options()
				if select_options and value not in select_options:
					options_string = ", ".join([frappe.bold(d) for d in select_options])
					msg = _("Value must be one of {0}").format(options_string)
					self.warnings.append(
						{
							"row": row_number,
							"field": df.as_dict(convert_dates_to_str=True),
							"message": msg,
						}
					)
					return False

			elif df.fieldtype == "Link":
				d = self.get_missing_link_field_values(df.options)
				if value in d.missing_values and not d.one_mandatory:
					msg = _("Value {0} missing for {1}").format(
						frappe.bold(value), frappe.bold(df.options)
					)
					self.warnings.append(
						{
							"row": row_number,
							"field": df.as_dict(convert_dates_to_str=True),
							"message": msg,
						}
					)
					return value

			return value

		def parse_doc(doctype, docfields, values, row_number):
			doc = frappe._dict()
			if self.import_type == INSERT:
				# new_doc returns a dict with default values set
				doc = frappe.new_doc(doctype, as_dict=True)

			# remove standard fields and __islocal
			for key in frappe.model.default_fields + ("__islocal",):
				doc.pop(key, None)

			for df, value in zip(docfields, values):
				if value in INVALID_VALUES:
					value = None

				value = validate_value(value, df)
				if value:
					doc[df.fieldname] = self.parse_value(value, df)

			is_table = frappe.get_meta(doctype).istable
			is_update = self.import_type == UPDATE
			if is_table and is_update and doc.get("name") in INVALID_VALUES:
				# for table rows being inserted in update
				# create a new doc with defaults set
				new_doc = frappe.new_doc(doctype, as_dict=True)
				new_doc.update(doc)
				doc = new_doc

			check_mandatory_fields(doctype, doc, row_number)
			return doc

		def check_mandatory_fields(doctype, doc, row_number):
			"""If import type is Insert:
				Check for mandatory fields (except table fields) in doc
			if import type is Update:
				Check for name field or autoname field in doc
			"""
			meta = frappe.get_meta(doctype)
			if self.import_type == UPDATE:
				if meta.istable:
					# when updating records with table rows,
					# there are two scenarios:
					# 1. if row 'name' is provided in the template
					# the table row will be updated
					# 2. if row 'name' is not provided
					# then a new row will be added
					# so we dont need to check for mandatory
					return

				id_field = self.get_id_field(doctype)
				if doc.get(id_field.fieldname) in INVALID_VALUES:
					self.warnings.append(
						{
							"row": row_number,
							"message": _("{0} is a mandatory field").format(id_field.label),
						}
					)
				return

			fields = [
				df
				for df in meta.fields
				if df.fieldtype not in table_fields
				and df.reqd
				and doc.get(df.fieldname) in INVALID_VALUES
			]

			if not fields:
				return

			if len(fields) == 1:
				self.warnings.append(
					{
						"row": row_number,
						"message": _("{0} is a mandatory field").format(fields[0].label),
					}
				)
			else:
				fields_string = ", ".join([df.label for df in fields])
				self.warnings.append(
					{"row": row_number, "message": _("{0} are mandatory fields").format(fields_string)}
				)

		parsed_docs = {}
		for row in rows:
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

				columns = [self.columns[i] for i in column_indexes]
				docfields = [col.df for col in columns]
				doc = parse_doc(doctype, docfields, values, row_number)
				parsed_docs[doctype] = parsed_docs.get(doctype, [])
				parsed_docs[doctype].append(doc)

		# build the doc with children
		doc = {}
		for doctype, docs in parsed_docs.items():
			if doctype == self.doctype:
				doc.update(docs[0])
			else:
				table_dfs = self.meta.get(
					"fields", {"options": doctype, "fieldtype": ["in", table_fields]}
				)
				if table_dfs:
					table_field = table_dfs[0]
					doc[table_field.fieldname] = docs

		# check if there is atleast one row for mandatory table fields
		mandatory_table_fields = [
			df
			for df in self.meta.fields
			if df.fieldtype in table_fields and df.reqd and len(doc.get(df.fieldname, [])) == 0
		]
		if len(mandatory_table_fields) == 1:
			self.warnings.append(
				{
					"row": first_row[0],
					"message": _("There should be atleast one row for {0} table").format(
						mandatory_table_fields[0].label
					),
				}
			)
		elif mandatory_table_fields:
			fields_string = ", ".join([df.label for df in mandatory_table_fields])
			message = _("There should be atleast one row for the following tables: {0}").format(
				fields_string
			)
			self.warnings.append({"row": first_row[0], "message": message})

		return doc, rows, data[len(rows) :]

	def process_doc(self, doc):
		if self.import_type == INSERT:
			return self.insert_record(doc)
		elif self.import_type == UPDATE:
			return self.update_record(doc)

	def insert_record(self, doc):
		self.create_missing_linked_records(doc)

		new_doc = frappe.new_doc(self.doctype)
		new_doc.update(doc)
		# name shouldn't be set when inserting a new record
		new_doc.set("name", None)
		new_doc.insert()
		if self.meta.is_submittable and self.data_import.submit_after_import:
			new_doc.submit()
		return new_doc

	def create_missing_linked_records(self, doc):
		"""
		Finds fields that are of type Link, and creates the corresponding
		document automatically if it has only one mandatory field
		"""
		link_values = []

		def get_link_fields(doc, doctype):
			for fieldname, value in doc.items():
				meta = frappe.get_meta(doctype)
				df = meta.get_field(fieldname)
				if not df:
					continue
				if df.fieldtype == "Link" and value not in INVALID_VALUES:
					link_values.append([df.options, value])
				elif df.fieldtype in table_fields:
					for row in value:
						get_link_fields(row, df.options)

		get_link_fields(doc, self.doctype)

		for link_doctype, link_value in link_values:
			d = self.missing_link_values.get(link_doctype)
			if d and d.one_mandatory and link_value in d.missing_values:
				# find the autoname field
				autoname_field = self.get_autoname_field(link_doctype)
				name_field = autoname_field.fieldname if autoname_field else "name"
				new_doc = frappe.new_doc(link_doctype)
				new_doc.set(name_field, link_value)
				new_doc.insert()
				d.missing_values.remove(link_value)

	def update_record(self, doc):
		id_fieldname = self.get_id_fieldname(self.doctype)
		id_value = doc[id_fieldname]
		existing_doc = frappe.get_doc(self.doctype, id_value)
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

		header_row = [col.header_title for col in self.columns[1:]]
		rows = [header_row]
		rows += [row[1:] for row in self.rows if row[0] in row_indexes]

		build_csv_response(rows, self.doctype)

	def get_missing_link_field_values(self, doctype):
		return self.missing_link_values.get(doctype, {})

	def prepare_missing_link_field_values(self):
		columns = self.columns
		rows = self.rows
		link_column_indexes = [
			col.index for col in columns if col.df and col.df.fieldtype == "Link"
		]

		self.missing_link_values = {}
		for index in link_column_indexes:
			col = columns[index]
			column_values = [row[index] for row in rows]
			values = set([v for v in column_values if v not in INVALID_VALUES])
			doctype = col.df.options

			missing_values = [value for value in values if not frappe.db.exists(doctype, value)]
			if self.missing_link_values.get(doctype):
				self.missing_link_values[doctype].missing_values += missing_values
			else:
				self.missing_link_values[doctype] = frappe._dict(
					missing_values=missing_values,
					one_mandatory=self.has_one_mandatory_field(doctype),
					df=col.df,
				)

	def get_eta(self, current, total, processing_time):
		remaining = total - current
		eta = processing_time * remaining
		if not self.last_eta or eta < self.last_eta:
			self.last_eta = eta
		return self.last_eta

	def has_one_mandatory_field(self, doctype):
		meta = frappe.get_meta(doctype)
		# get mandatory fields with default not set
		mandatory_fields = [df for df in meta.fields if df.reqd and not df.default]
		mandatory_fields_count = len(mandatory_fields)
		if meta.autoname and meta.autoname.lower() == "prompt":
			mandatory_fields_count += 1
		return mandatory_fields_count == 1

	def get_id_fieldname(self, doctype):
		return self.get_id_field(doctype).fieldname

	def get_id_field(self, doctype):
		autoname_field = self.get_autoname_field(doctype)
		if autoname_field:
			return autoname_field
		return frappe._dict({"label": "ID", "fieldname": "name", "fieldtype": "Data"})

	def get_autoname_field(self, doctype):
		meta = frappe.get_meta(doctype)
		if meta.autoname and meta.autoname.startswith("field:"):
			fieldname = meta.autoname[len("field:") :]
			return meta.get_field(fieldname)

	def print_grouped_warnings(self, warnings):
		warnings_by_row = {}
		other_warnings = []
		for w in warnings:
			if w.get("row"):
				warnings_by_row.setdefault(w.get("row"), []).append(w)
			else:
				other_warnings.append(w)

		for row_number, warnings in warnings_by_row.items():
			print("Row {0}".format(row_number))
			for w in warnings:
				print(w.get("message"))

		for w in other_warnings:
			print(w.get("message"))

	def print_import_log(self, import_log):
		failed_records = [l for l in import_log if not l.success]
		successful_records = [l for l in import_log if l.success]

		if successful_records:
			print(
				"Successfully imported {0} records out of {1}".format(
					len(successful_records), len(import_log)
				)
			)

		if failed_records:
			print("Failed to import {0} records".format(len(failed_records)))
			file_name = "{0}_import_on_{1}.txt".format(self.doctype, frappe.utils.now())
			print("Check {0} for errors".format(os.path.join("sites", file_name)))
			text = ""
			for w in failed_records:
				text += "Row Indexes: {0}\n".format(str(w.get("row_indexes", [])))
				text += "Messages:\n{0}\n".format("\n".join(w.get("messages", [])))
				text += "Traceback:\n{0}\n\n".format(w.get("exception"))

			with open(file_name, "w") as f:
				f.write(text)


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
			# if date is parsed without any exception
			# capture the date format
			datetime.strptime(_date, f)
			date_format = f
			break
		except ValueError:
			pass

	if _time:
		for f in TIME_FORMATS:
			try:
				# if time is parsed without any exception
				# capture the time format
				datetime.strptime(_time, f)
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
