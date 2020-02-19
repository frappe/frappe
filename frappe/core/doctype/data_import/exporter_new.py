# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.model import display_fieldtypes, no_value_fields, table_fields
from frappe.utils.csvutils import build_csv_response
from frappe.utils.xlsxutils import build_xlsx_response
from .importer_new import INVALID_VALUES


class Exporter:
	def __init__(
		self,
		doctype,
		export_fields=None,
		export_data=False,
		export_filters=None,
		export_page_length=None,
		file_type="CSV",
	):
		"""
		Exports records of a DocType for use with Importer
			:param doctype: Document Type to export
			:param export_fields=None: One of 'All', 'Mandatory' or {'DocType': ['field1', 'field2'], 'Child DocType': ['childfield1']}
			:param export_data=False: Whether to export data as well
			:param export_filters=None: The filters (dict or list) which is used to query the records
			:param file_type: One of 'Excel' or 'CSV'
		"""
		self.doctype = doctype
		self.meta = frappe.get_meta(doctype)
		self.export_fields = export_fields
		self.export_filters = export_filters
		self.export_page_length = export_page_length
		self.file_type = file_type

		# this will contain the csv content
		self.csv_array = []

		# fields that get exported
		# can be All, Mandatory or User Selected Fields
		self.fields = self.get_all_exportable_fields()
		self.add_header()

		if export_data:
			self.data = self.get_data_to_export()
		else:
			self.data = []
		self.add_data()

	def get_all_exportable_fields(self):
		return self.get_exportable_parent_fields() + self.get_exportable_children_fields()

	def get_exportable_parent_fields(self):
		parent_fields = self.get_exportable_fields(self.doctype)

		# if autoname is based on field
		# then merge ID and the field column title as "ID (Autoname Field)"
		autoname = self.meta.autoname
		if autoname and autoname.startswith("field:"):
			fieldname = autoname[len("field:") :]
			autoname_field = self.meta.get_field(fieldname)
			if autoname_field:
				name_field = parent_fields[0]
				name_field.label = "ID ({})".format(autoname_field.label)
				# remove the autoname field as it is a duplicate of ID field
				parent_fields = [
					df for df in parent_fields if df.fieldname != autoname_field.fieldname
				]

		return parent_fields

	def get_exportable_children_fields(self):
		children = [df.options for df in self.meta.fields if df.fieldtype in table_fields]
		children_fields = []
		for child in children:
			children_fields += self.get_exportable_fields(child)

		return children_fields

	def get_exportable_fields(self, doctype):
		meta = frappe.get_meta(doctype)

		def is_exportable(df):
			return df and df.fieldtype not in (display_fieldtypes + no_value_fields)

		# filter out invalid fieldtypes
		all_fields = [df for df in meta.fields if is_exportable(df)]
		# add name field
		name_field = frappe._dict(
			{
				"fieldtype": "Data",
				"fieldname": "name",
				"label": "ID",
				"reqd": 1,
				"parent": doctype,
			}
		)
		all_fields = [name_field] + all_fields

		if self.export_fields == "Mandatory":
			fields = [df for df in all_fields if df.reqd]

		if self.export_fields == "All":
			fields = list(all_fields)

		elif isinstance(self.export_fields, dict):
			fields_to_export = self.export_fields.get(doctype, [])
			fields = [meta.get_field(fieldname) for fieldname in fields_to_export]
			fields = [df for df in fields if is_exportable(df)]
			if 'name' in fields_to_export:
				fields = [name_field] + fields

		return fields or []

	def get_data_to_export(self):
		frappe.permissions.can_export(self.doctype, raise_exception=True)

		def get_column_name(df):
			return "`tab{0}`.`{1}`".format(df.parent, df.fieldname)

		fields = [get_column_name(df) for df in self.fields]
		filters = self.export_filters

		if self.meta.is_nested_set():
			order_by = "`tab{0}`.`lft` ASC".format(self.doctype)
		else:
			order_by = "`tab{0}`.`creation` DESC".format(self.doctype)

		data = frappe.db.get_list(
			self.doctype,
			filters=filters,
			fields=fields,
			limit_page_length=self.export_page_length,
			order_by=order_by,
			as_list=1,
		)

		data = self.remove_duplicate_values(data)
		data = self.remove_row_gaps(data)
		data = self.remove_empty_rows(data)
		# data = self.remove_values_from_name_column(data)

		return data

	def remove_duplicate_values(self, data):
		out = []

		doctypes = set([df.parent for df in self.fields])

		def name_exists_in_column_before_row(name, column_index, row_index):
			column_values = [row[column_index] for i, row in enumerate(data) if i < row_index]
			return name in column_values

		for i, row in enumerate(data):
			# first row is fine
			if i == 0:
				out.append(row)
				continue

			row = list(row)
			for doctype in doctypes:
				name_index = self.get_name_column_index(doctype)
				name = row[name_index]
				column_indexes = self.get_column_indexes(doctype)

				if name_exists_in_column_before_row(name, name_index, i):
					# remove the values from the row
					row = [None if i in column_indexes else d for i, d in enumerate(row)]

			out.append(row)

		return out

	def remove_row_gaps(self, data):
		doctypes = set([df.parent for df in self.fields if df.parent != self.doctype])

		def get_nearest_empty_row_index(col_index, row_index):
			col_values = [row[col_index] for row in data]
			i = row_index - 1
			while not col_values[i]:
				i = i - 1
			out = i + 1
			if row_index != out:
				return out

		for i, row in enumerate(data):
			# if this is the row that contains parent values then skip
			if row[0]:
				continue

			for doctype in doctypes:
				name_index = self.get_name_column_index(doctype)
				name = row[name_index]
				column_indexes = self.get_column_indexes(doctype)

				if not name:
					continue

				row_index = get_nearest_empty_row_index(name_index, i)
				if row_index:
					for col_index in column_indexes:
						data[row_index][col_index] = row[col_index]
						row[col_index] = None

		return data

	# pylint: disable=R0201
	def remove_empty_rows(self, data):
		return [row for row in data if any(v not in INVALID_VALUES for v in row)]

	def remove_values_from_name_column(self, data):
		out = []
		name_columns = [i for i, df in enumerate(self.fields) if df.fieldname == "name"]
		for row in data:
			out.append(["" if i in name_columns else value for i, value in enumerate(row)])
		return out

	def get_name_column_index(self, doctype):
		for i, df in enumerate(self.fields):
			if df.parent == doctype and df.fieldname == "name":
				return i
		return -1

	def get_column_indexes(self, doctype):
		return [i for i, df in enumerate(self.fields) if df.parent == doctype]

	def add_header(self):
		def get_label(df):
			if df.parent == self.doctype:
				return df.label
			else:
				return "{0} ({1})".format(df.label, df.parent)

		header = [get_label(df) for df in self.fields]
		self.csv_array.append(header)

	def add_data(self):
		self.csv_array += self.data

	def get_csv_array(self):
		return self.csv_array

	def get_csv_array_for_export(self):
		csv_array = self.csv_array

		if not self.data:
			# add 2 empty rows
			csv_array += [[]] * 2

		return csv_array

	def build_response(self):
		if self.file_type == 'CSV':
			self.build_csv_response()
		elif self.file_type == 'Excel':
			self.build_xlsx_response()

	def build_csv_response(self):
		build_csv_response(self.get_csv_array_for_export(), self.doctype)

	def build_xlsx_response(self):
		build_xlsx_response(self.get_csv_array_for_export(), self.doctype)
