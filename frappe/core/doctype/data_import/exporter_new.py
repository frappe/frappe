# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _
from frappe.model import display_fieldtypes, no_value_fields, table_fields
from frappe.utils.csvutils import build_csv_response

class Exporter:
	def __init__(self, doctype, export_fields=None, export_data=False, export_filters=None, file_type='CSV'):
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

		# this will contain the csv content
		self.csv_array = []

		# fields that get exported
		# can be All, Mandatory or User Selected Fields
		self.fields = self.get_all_exportable_fields()
		self.add_header()

		if export_data:
			self.data = self.get_data_to_export(export_filters)
		else:
			self.data = []
		self.add_data()


	def get_all_exportable_fields(self):
		return self.get_exportable_parent_fields() + self.get_exportable_children_fields()


	def get_exportable_parent_fields(self):
		name_field = frappe._dict({
			'fieldtype': 'Data',
			'fieldname': 'name',
			'label': 'ID',
			'reqd': 1,
			'parent': self.doctype
		})
		return [name_field] + self.get_exportable_fields(self.doctype)


	def get_exportable_children_fields(self):
		children = [df.options for df in self.meta.fields if df.fieldtype in table_fields]
		children_fields = []
		for child in children:
			children_fields += self.get_exportable_fields(child)

		return children_fields


	def get_exportable_fields(self, doctype):
		def is_exportable(df):
			return (
				df.fieldtype not in display_fieldtypes
				and df.fieldtype not in no_value_fields
				and not df.hidden
			)

		meta = frappe.get_meta(doctype)

		# filter out layout fields
		fields = [df for df in meta.fields if is_exportable(df)]

		if self.export_fields == 'All':
			return fields

		if self.export_fields == 'Mandatory':
			return [df for df in fields if df.reqd]

		if isinstance(self.export_fields, dict):
			whitelist = self.export_fields.get(doctype, [])
			return [df for df in fields if df.fieldname in whitelist]

		return [df for df in fields if df.reqd or df.in_list_view or df.bold]


	def get_data_to_export(self, filters=None):
		frappe.permissions.can_export(self.doctype, raise_exception=True)

		def get_column_name(df):
			return '`tab{0}`.`{1}`'.format(df.parent, df.fieldname)

		fieldnames = [get_column_name(df) for df in self.fields]

		if self.meta.is_nested_set():
			order_by = '`tab{0}`.`lft` ASC'.format(self.doctype)
		else:
			order_by = '`tab{0}`.`creation` DESC'.format(self.doctype)

		data = frappe.db.get_list(self.doctype,
			filters=filters,
			fields=fieldnames,
			limit_page_length=None,
			order_by=order_by,
			as_list=1,
		)

		return self.remove_duplicate_parent_values(data)

	def remove_duplicate_parent_values(self, data):
		out = []

		parent_fields = self.get_exportable_parent_fields()
		parent_fields_count = len(parent_fields)

		current_name = None
		# first column is always name, can be used to find duplicate rows
		for row in data:
			row = list(row)
			name = row[0]

			if name != current_name:
				current_name = name
				out.append(row)

			elif name == current_name:
				# remove the parent values from the row
				row = row[parent_fields_count:]
				# replace them with None values and add back the row contents
				row = [None] * parent_fields_count + row
				out.append(row)

		return out


	def add_header(self):
		def get_label(df):
			if df.parent == self.doctype:
				return df.label
			else:
				return '{0} / {1}'.format(df.parent, df.label)

		header = [get_label(df) for df in self.fields]
		self.csv_array.append(header)


	def add_data(self):
		self.csv_array += self.data


	def get_csv_array(self):
		return self.csv_array

	def build_csv_response(self):
		csv_array = self.csv_array

		if not self.data:
			# add 5 empty rows
			csv_array += [[]] * 5

		build_csv_response(csv_array, self.doctype)
