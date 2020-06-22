# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import os
import io
import frappe
import timeit
import json
from datetime import datetime
from frappe import _
from frappe.utils import cint, flt, update_progress_bar, cstr
from frappe.utils.csvutils import read_csv_content, get_csv_content_from_google_sheets
from frappe.utils.xlsxutils import (
	read_xlsx_file_from_attached_file,
	read_xls_file_from_attached_file,
)
from frappe.model import no_value_fields, table_fields as table_fieldtypes

INVALID_VALUES = ("", None)
MAX_ROWS_IN_PREVIEW = 10
INSERT = "Insert New Records"
UPDATE = "Update Existing Records"


class Importer:
	def __init__(
		self, doctype, data_import=None, file_path=None, import_type=None, console=False
	):
		self.doctype = doctype
		self.console = console

		self.data_import = data_import
		if not self.data_import:
			self.data_import = frappe.get_doc(doctype="Data Import")
			if import_type:
				self.data_import.import_type = import_type

		self.template_options = frappe.parse_json(self.data_import.template_options or "{}")
		self.import_type = self.data_import.import_type

		self.import_file = ImportFile(
			doctype,
			file_path or data_import.google_sheets_url or data_import.import_file,
			self.template_options,
			self.import_type,
		)

	def get_data_for_import_preview(self):
		return self.import_file.get_data_for_import_preview()

	def before_import(self):
		# set user lang for translations
		frappe.cache().hdel("lang", frappe.session.user)
		frappe.set_user_lang(frappe.session.user)

		# set flags
		frappe.flags.in_import = True
		frappe.flags.mute_emails = self.data_import.mute_emails

		self.data_import.db_set("template_warnings", "")

	def import_data(self):
		self.before_import()

		# parse docs from rows
		payloads = self.import_file.get_payloads_for_import()

		# dont import if there are non-ignorable warnings
		warnings = self.import_file.get_warnings()
		warnings = [w for w in warnings if w.get("type") != "info"]

		if warnings:
			if self.console:
				self.print_grouped_warnings(warnings)
			else:
				self.data_import.db_set("template_warnings", json.dumps(warnings))
			return

		# setup import log
		if self.data_import.import_log:
			import_log = frappe.parse_json(self.data_import.import_log)
		else:
			import_log = []

		# remove previous failures from import log
		import_log = [log for log in import_log if log.get("success")]

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
				row_indexes = [row.row_number for row in payload.rows]
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

					if self.console:
						update_progress_bar(
							"Importing {0} records".format(total_payload_count),
							current_index,
							total_payload_count,
						)
					elif total_payload_count > 5:
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
		failures = [log for log in import_log if not log.get("success")]
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

		self.after_import()

		return import_log

	def after_import(self):
		frappe.flags.in_import = False
		frappe.flags.mute_emails = False

	def process_doc(self, doc):
		if self.import_type == INSERT:
			return self.insert_record(doc)
		elif self.import_type == UPDATE:
			return self.update_record(doc)

	def insert_record(self, doc):
		meta = frappe.get_meta(self.doctype)
		new_doc = frappe.new_doc(self.doctype)
		new_doc.update(doc)

		if (meta.autoname or "").lower() != "prompt":
			# name can only be set directly if autoname is prompt
			new_doc.set("name", None)

		new_doc.flags.updater_reference = {
			"doctype": self.data_import.doctype,
			"docname": self.data_import.name,
			"label": _("via Data Import"),
		}

		new_doc.insert()
		if meta.is_submittable and self.data_import.submit_after_import:
			new_doc.submit()
		return new_doc

	def update_record(self, doc):
		id_field = get_id_field(self.doctype)
		existing_doc = frappe.get_doc(self.doctype, doc.get(id_field.fieldname))
		existing_doc.flags.updater_reference = {
			"doctype": self.data_import.doctype,
			"docname": self.data_import.name,
			"label": _("via Data Import"),
		}
		existing_doc.update(doc)
		existing_doc.save()
		return existing_doc

	def get_eta(self, current, total, processing_time):
		self.last_eta = getattr(self, "last_eta", 0)
		remaining = total - current
		eta = processing_time * remaining
		if not self.last_eta or eta < self.last_eta:
			self.last_eta = eta
		return self.last_eta

	def export_errored_rows(self):
		from frappe.utils.csvutils import build_csv_response

		if not self.data_import:
			return

		import_log = frappe.parse_json(self.data_import.import_log or "[]")
		failures = [log for log in import_log if not log.get("success")]
		row_indexes = []
		for f in failures:
			row_indexes.extend(f.get("row_indexes", []))

		# de duplicate
		row_indexes = list(set(row_indexes))
		row_indexes.sort()

		header_row = [col.header_title for col in self.import_file.columns]
		rows = [header_row]
		rows += [row.data for row in self.import_file.data if row.row_number in row_indexes]

		build_csv_response(rows, self.doctype)

	def print_import_log(self, import_log):
		failed_records = [log for log in import_log if not log.success]
		successful_records = [log for log in import_log if log.success]

		if successful_records:
			print()
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


class ImportFile:
	def __init__(self, doctype, file, template_options=None, import_type=None):
		self.doctype = doctype
		self.template_options = template_options or frappe._dict(
			column_to_field_map=frappe._dict()
		)
		self.column_to_field_map = self.template_options.column_to_field_map
		self.import_type = import_type

		self.file_doc = self.file_path = None
		if isinstance(file, frappe.string_types):
			if frappe.db.exists("File", {"file_url": file}):
				self.file_doc = frappe.get_doc("File", {"file_url": file})
			elif 'docs.google.com/spreadsheets' in file:
				self.google_sheets_url = file
			elif os.path.exists(file):
				self.file_path = file

		if not self.file_doc and not self.file_path and not self.google_sheets_url:
			frappe.throw(_("Invalid template file for import"))

		self.raw_data = self.get_data_from_template_file()
		self.parse_data_from_template()

	def get_data_from_template_file(self):
		content = None
		extension = None

		if self.file_doc:
			parts = self.file_doc.get_extension()
			extension = parts[1]
			content = self.file_doc.get_content()
			extension = extension.lstrip(".")

		elif self.file_path:
			content, extension = self.read_file(self.file_path)

		elif self.google_sheets_url:
			content = get_csv_content_from_google_sheets(self.google_sheets_url)
			extension = 'csv'

		if not content:
			frappe.throw(_("Invalid or corrupted content for import"))

		if not extension:
			extension = "csv"

		if content:
			return self.read_content(content, extension)

	def parse_data_from_template(self):
		header = None
		data = []

		for i, row in enumerate(self.raw_data):
			if all(v in INVALID_VALUES for v in row):
				# empty row
				continue

			if not header:
				header = Header(i, row, self.doctype, self.raw_data, self.column_to_field_map)
			else:
				row_obj = Row(i, row, self.doctype, header, self.import_type)
				data.append(row_obj)

		self.header = header
		self.columns = self.header.columns
		self.data = data

		if len(data) < 1:
			frappe.throw(
				_("Import template should contain a Header and atleast one row."),
				title=_("Template Error"),
			)

	def get_data_for_import_preview(self):
		"""Adds a serial number column as the first column"""

		columns = [frappe._dict({"header_title": "Sr. No", "skip_import": True})]
		columns += [col.as_dict() for col in self.columns]
		for col in columns:
			# only pick useful fields in docfields to minimise the payload
			if col.df:
				col.df = {
					"fieldtype": col.df.fieldtype,
					"fieldname": col.df.fieldname,
					"label": col.df.label,
					"options": col.df.options,
					"parent": col.df.parent,
					"reqd": col.df.reqd,
					"default": col.df.default,
					"read_only": col.df.read_only,
				}

		data = [[row.row_number] + row.as_list() for row in self.data]

		warnings = self.get_warnings()

		out = frappe._dict()
		out.data = data
		out.columns = columns
		out.warnings = warnings
		total_number_of_rows = len(out.data)
		if total_number_of_rows > MAX_ROWS_IN_PREVIEW:
			out.data = out.data[:MAX_ROWS_IN_PREVIEW]
			out.max_rows_exceeded = True
			out.max_rows_in_preview = MAX_ROWS_IN_PREVIEW
			out.total_number_of_rows = total_number_of_rows
		return out

	def get_payloads_for_import(self):
		payloads = []
		# make a copy
		data = list(self.data)
		while data:
			doc, rows, data = self.parse_next_row_for_import(data)
			payloads.append(frappe._dict(doc=doc, rows=rows))
		return payloads

	def parse_next_row_for_import(self, data):
		"""
		Parses rows that make up a doc. A doc maybe built from a single row or multiple rows.
		Returns the doc, rows, and data without the rows.
		"""
		doctypes = self.header.doctypes

		# first row is included by default
		first_row = data[0]
		rows = [first_row]

		# if there are child doctypes, find the subsequent rows
		if len(doctypes) > 1:
			# subsequent rows either dont have any parent value set
			# or have the same value as the parent row
			# we include a row if either of conditions match
			parent_column_indexes = self.header.get_column_indexes(self.doctype)
			parent_row_values = first_row.get_values(parent_column_indexes)

			data_without_first_row = data[1:]
			for row in data_without_first_row:
				row_values = row.get_values(parent_column_indexes)
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

		parent_doc = None
		for row in rows:
			for doctype, table_df in doctypes:
				if doctype == self.doctype and not parent_doc:
					parent_doc = row.parse_doc(doctype)

				if doctype != self.doctype and table_df:
					child_doc = row.parse_doc(doctype, parent_doc, table_df)
					parent_doc[table_df.fieldname] = parent_doc.get(table_df.fieldname, [])
					parent_doc[table_df.fieldname].append(child_doc)

		doc = parent_doc
		# check if there is atleast one row for mandatory table fields
		meta = frappe.get_meta(self.doctype)
		mandatory_table_fields = [
			df
			for df in meta.fields
			if df.fieldtype in table_fieldtypes
			and df.reqd
			and len(doc.get(df.fieldname, [])) == 0
		]
		if len(mandatory_table_fields) == 1:
			self.warnings.append(
				{
					"row": first_row.row_number,
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
			self.warnings.append({"row": first_row.row_number, "message": message})

		return doc, rows, data[len(rows) :]

	def get_warnings(self):
		warnings = []
		for col in self.header.columns:
			warnings += col.warnings

		for row in self.data:
			warnings += row.warnings

		return warnings

	######

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

		return data


class Row:
	link_values_exist_map = {}

	def __init__(self, index, row, doctype, header, import_type):
		self.index = index
		self.row_number = index + 1
		self.doctype = doctype
		self.data = row
		self.header = header
		self.import_type = import_type
		self.warnings = []

		len_row = len(self.data)
		len_columns = len(self.header.columns)
		if len_row != len_columns:
			less_than_columns = len_row < len_columns
			message = (
				"Row has less values than columns"
				if less_than_columns
				else "Row has more values than columns"
			)
			self.warnings.append(
				{"row": self.row_number, "message": message,}
			)

	def parse_doc(self, doctype, parent_doc=None, table_df=None):
		col_indexes = self.header.get_column_indexes(doctype, table_df)
		values = self.get_values(col_indexes)
		columns = self.header.get_columns(col_indexes)
		doc = self._parse_doc(doctype, columns, values, parent_doc, table_df)
		return doc

	def _parse_doc(self, doctype, columns, values, parent_doc=None, table_df=None):
		doc = frappe._dict()
		if self.import_type == INSERT:
			# new_doc returns a dict with default values set
			doc = frappe.new_doc(
				doctype,
				parent_doc=parent_doc,
				parentfield=table_df.fieldname if table_df else None,
				as_dict=True,
			)

		# remove standard fields and __islocal
		for key in frappe.model.default_fields + ("__islocal",):
			doc.pop(key, None)

		for col, value in zip(columns, values):
			df = col.df
			if value in INVALID_VALUES:
				value = None

			if value is not None:
				value = self.validate_value(value, col)

			if value is not None:
				doc[df.fieldname] = self.parse_value(value, col)

		is_table = frappe.get_meta(doctype).istable
		is_update = self.import_type == UPDATE
		if is_table and is_update and doc.get("name") in INVALID_VALUES:
			# for table rows being inserted in update
			# create a new doc with defaults set
			new_doc = frappe.new_doc(doctype, as_dict=True)
			new_doc.update(doc)
			doc = new_doc

		self.check_mandatory_fields(doctype, doc, table_df)
		return doc

	def validate_value(self, value, col):
		df = col.df
		if df.fieldtype == "Select":
			select_options = df.get_select_options()
			if select_options and value not in select_options:
				options_string = ", ".join([frappe.bold(d) for d in select_options])
				msg = _("Value must be one of {0}").format(options_string)
				self.warnings.append(
					{
						"row": self.row_number,
						"field": df.as_dict(convert_dates_to_str=True),
						"message": msg,
					}
				)
				return

		elif df.fieldtype == "Link":
			exists = self.link_exists(value, df)
			if not exists:
				msg = _("Value {0} missing for {1}").format(
					frappe.bold(value), frappe.bold(df.options)
				)
				self.warnings.append(
					{
						"row": self.row_number,
						"field": df.as_dict(convert_dates_to_str=True),
						"message": msg,
					}
				)
				return
		elif df.fieldtype in ["Date", "Datetime"]:
			value = self.get_date(value, col)
			if isinstance(value, frappe.string_types):
				# value was not parsed as datetime object
				self.warnings.append(
					{
						"row": self.row_number,
						"col": col.column_number,
						"field": df.as_dict(convert_dates_to_str=True),
						"message": _("Value {0} must in {1} format").format(
							frappe.bold(value), frappe.bold(get_user_format(col.date_format))
						),
					}
				)
				return

		return value

	def link_exists(self, value, df):
		key = df.options + "::" + value
		if Row.link_values_exist_map.get(key) is None:
			Row.link_values_exist_map[key] = frappe.db.exists(df.options, value)
		return Row.link_values_exist_map.get(key)

	def parse_value(self, value, col):
		df = col.df
		if isinstance(value, datetime) and df.fieldtype in ["Date", "Datetime"]:
			return value

		value = cstr(value)

		# convert boolean values to 0 or 1
		valid_check_values = ["t", "f", "true", "false", "yes", "no", "y", "n"]
		if df.fieldtype == "Check" and value.lower().strip() in valid_check_values:
			value = value.lower().strip()
			value = 1 if value in ["t", "true", "y", "yes"] else 0

		if df.fieldtype in ["Int", "Check"]:
			value = cint(value)
		elif df.fieldtype in ["Float", "Percent", "Currency"]:
			value = flt(value)
		elif df.fieldtype in ["Date", "Datetime"]:
			value = self.get_date(value, col)

		return value

	def get_date(self, value, column):
		date_format = column.date_format
		if date_format:
			try:
				return datetime.strptime(value, date_format)
			except ValueError:
				# ignore date values that dont match the format
				# import will break for these values later
				pass
		return value

	def check_mandatory_fields(self, doctype, doc, table_df=None):
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

			# for update, only ID (name) field is mandatory
			id_field = get_id_field(doctype)
			if doc.get(id_field.fieldname) in INVALID_VALUES:
				self.warnings.append(
					{
						"row": self.row_number,
						"message": _("{0} is a mandatory field asdadsf").format(id_field.label),
					}
				)
			return

		fields = [
			df
			for df in meta.fields
			if df.fieldtype not in table_fieldtypes
			and df.reqd
			and doc.get(df.fieldname) in INVALID_VALUES
		]

		if not fields:
			return

		def get_field_label(df):
			return "{0}{1}".format(df.label, " ({})".format(table_df.label) if table_df else "")

		if len(fields) == 1:
			field_label = get_field_label(fields[0])
			self.warnings.append(
				{
					"row": self.row_number,
					"message": _("{0} is a mandatory field").format(frappe.bold(field_label)),
				}
			)
		else:
			fields_string = ", ".join([frappe.bold(get_field_label(df)) for df in fields])
			self.warnings.append(
				{
					"row": self.row_number,
					"message": _("{0} are mandatory fields").format(fields_string),
				}
			)

	def get_values(self, indexes):
		return [self.data[i] for i in indexes]

	def get(self, index):
		return self.data[index]

	def as_list(self):
		return self.data


class Header(Row):
	def __init__(self, index, row, doctype, raw_data, column_to_field_map):
		self.index = index
		self.row_number = index + 1
		self.data = row
		self.doctype = doctype

		self.seen = []
		self.columns = []

		for j, header in enumerate(row):
			column_values = [get_item_at_index(r, j) for r in raw_data]
			column = Column(
				j, header, self.doctype, column_values, column_to_field_map.get(header), self.seen
			)
			self.seen.append(header)
			self.columns.append(column)

		doctypes = []
		for col in self.columns:
			if not col.df:
				continue
			if col.df.parent == self.doctype:
				doctypes.append((col.df.parent, None))
			else:
				doctypes.append((col.df.parent, col.df.child_table_df))

		self.doctypes = sorted(
			list(set(doctypes)), key=lambda x: -1 if x[0] == self.doctype else 1
		)

	def get_column_indexes(self, doctype, tablefield=None):
		def is_table_field(df):
			if tablefield:
				return df.child_table_df.fieldname == tablefield.fieldname
			return True

		return [
			col.index
			for col in self.columns
			if not col.skip_import
			and col.df
			and col.df.parent == doctype
			and is_table_field(col.df)
		]

	def get_columns(self, indexes):
		return [self.columns[i] for i in indexes]


class Column:
	seen = []
	fields_column_map = {}

	def __init__(self, index, header, doctype, column_values, map_to_field=None, seen=[]):
		self.index = index
		self.column_number = index + 1
		self.doctype = doctype
		self.header_title = header
		self.column_values = column_values
		self.map_to_field = map_to_field
		self.seen = seen

		self.date_format = None
		self.df = None
		self.skip_import = None
		self.warnings = []

		self.meta = frappe.get_meta(doctype)
		self.parse()
		self.parse_date_format()

	def parse(self):
		header_title = self.header_title
		column_number = str(self.column_number)
		skip_import = False

		if self.map_to_field and self.map_to_field != "Don't Import":
			df = get_df_for_column_header(self.doctype, self.map_to_field)
			if df:
				self.warnings.append(
					{
						"message": _("Mapping column {0} to field {1}").format(
							frappe.bold(header_title or "<i>Untitled Column</i>"), frappe.bold(df.label)
						),
						"type": "info",
					}
				)
			else:
				self.warnings.append(
					{
						"message": _("Could not map column {0} to field {1}").format(
							column_number, self.map_to_field
						),
						"type": "info",
					}
				)
		else:
			df = get_df_for_column_header(self.doctype, header_title)
			# df = df_by_labels_and_fieldnames.get(header_title)

		if not df:
			skip_import = True
		else:
			skip_import = False

		if header_title in self.seen:
			self.warnings.append(
				{
					"col": column_number,
					"message": _("Skipping Duplicate Column {0}").format(frappe.bold(header_title)),
					"type": "info",
				}
			)
			df = None
			skip_import = True
		elif self.map_to_field == "Don't Import":
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

		self.df = df
		self.skip_import = skip_import

	def parse_date_format(self):
		if self.df and self.df.fieldtype in ("Date", "Time", "Datetime"):
			self.date_format = self.guess_date_format_for_column()

	def guess_date_format_for_column(self):
		""" Guesses date format for a column by parsing all the values in the column,
		getting the date format and then returning the one which has the maximum frequency
		"""

		date_formats = [
			frappe.utils.guess_date_format(d) for d in self.column_values if isinstance(d, str)
		]
		date_formats = [d for d in date_formats if d]
		if not date_formats:
			return

		unique_date_formats = set(date_formats)
		max_occurred_date_format = max(unique_date_formats, key=date_formats.count)

		if len(unique_date_formats) > 1:
			# fmt: off
			message = _("The column {0} has {1} different date formats. Automatically setting {2} as the default format as it is the most common. Please change other values in this column to this format.")
			# fmt: on
			user_date_format = get_user_format(max_occurred_date_format)
			self.warnings.append(
				{
					"col": self.column_number,
					"message": message.format(
						frappe.bold(self.header_title),
						len(unique_date_formats),
						frappe.bold(user_date_format),
					),
					"type": "info",
				}
			)

		return max_occurred_date_format

	def as_dict(self):
		d = frappe._dict()
		d.index = self.index
		d.column_number = self.column_number
		d.doctype = self.doctype
		d.header_title = self.header_title
		d.map_to_field = self.map_to_field
		d.date_format = self.date_format
		d.df = self.df
		d.skip_import = self.skip_import
		d.warnings = self.warnings
		return d


def build_fields_dict_for_column_matching(parent_doctype):
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

	def get_standard_fields(doctype):
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

	parent_meta = frappe.get_meta(parent_doctype)
	out = {}

	# doctypes and fieldname if it is a child doctype
	doctypes = [[parent_doctype, None]] + [
		[df.options, df] for df in parent_meta.get_table_fields()
	]

	for doctype, table_df in doctypes:
		# name field
		name_by_label = (
			"ID" if doctype == parent_doctype else "ID ({0})".format(table_df.label)
		)
		name_by_fieldname = (
			"name" if doctype == parent_doctype else "{0}.name".format(table_df.fieldname)
		)
		name_df = frappe._dict(
			{
				"fieldtype": "Data",
				"fieldname": "name",
				"label": "ID",
				"reqd": 1,  # self.import_type == UPDATE,
				"parent": doctype,
			}
		)

		if doctype != parent_doctype:
			name_df.is_child_table_field = True
			name_df.child_table_df = table_df

		out[name_by_label] = name_df
		out[name_by_fieldname] = name_df

		# other fields
		fields = get_standard_fields(doctype) + frappe.get_meta(doctype).fields
		for df in fields:
			fieldtype = df.fieldtype or "Data"
			parent = df.parent or parent_doctype
			if fieldtype not in no_value_fields:
				if parent_doctype == doctype:
					# for parent doctypes keys will be
					# Label
					# label
					# Label (label)
					if not out.get(df.label):
						# if Label is already set, don't set it again
						# in case of duplicate column headers
						out[df.label] = df
					out[df.fieldname] = df
					label_with_fieldname = "{0} ({1})".format(df.label, df.fieldname)
					out[label_with_fieldname] = df
				else:
					# in case there are multiple table fields with the same doctype
					# for child doctypes keys will be
					# Label (Table Field Label)
					# table_field.fieldname
					table_fields = parent_meta.get(
						"fields", {"fieldtype": ["in", table_fieldtypes], "options": parent}
					)
					for table_field in table_fields:
						by_label = "{0} ({1})".format(df.label, table_field.label)
						by_fieldname = "{0}.{1}".format(table_field.fieldname, df.fieldname)

						# create a new df object to avoid mutation problems
						if isinstance(df, dict):
							new_df = frappe._dict(df.copy())
						else:
							new_df = df.as_dict()

						new_df.is_child_table_field = True
						new_df.child_table_df = table_field
						out[by_label] = new_df
						out[by_fieldname] = new_df

	# if autoname is based on field
	# add an entry for "ID (Autoname Field)"
	autoname_field = get_autoname_field(parent_doctype)
	if autoname_field:
		out["ID ({})".format(autoname_field.label)] = autoname_field
		# ID field should also map to the autoname field
		out["ID"] = autoname_field
		out["name"] = autoname_field

	return out


def get_df_for_column_header(doctype, header):
	def build_fields_dict_for_doctype():
		return build_fields_dict_for_column_matching(doctype)

	df_by_labels_and_fieldname = frappe.cache().hget(
		"data_import_column_header_map", doctype, generator=build_fields_dict_for_doctype
	)
	return df_by_labels_and_fieldname.get(header)


# utilities


def get_id_field(doctype):
	autoname_field = get_autoname_field(doctype)
	if autoname_field:
		return autoname_field
	return frappe._dict({"label": "ID", "fieldname": "name", "fieldtype": "Data"})


def get_autoname_field(doctype):
	meta = frappe.get_meta(doctype)
	if meta.autoname and meta.autoname.startswith("field:"):
		fieldname = meta.autoname[len("field:") :]
		return meta.get_field(fieldname)


def get_item_at_index(_list, i, default=None):
	try:
		a = _list[i]
	except IndexError:
		a = default
	return a


def get_user_format(date_format):
	return (
		date_format.replace("%Y", "yyyy")
		.replace("%y", "yy")
		.replace("%m", "mm")
		.replace("%d", "dd")
	)
