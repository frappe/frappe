# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model import display_fieldtypes, no_value_fields
from frappe.model import table_fields as table_fieldtypes
from frappe.utils import flt, format_duration, groupby_metric
from frappe.utils.csvutils import build_csv_response
from frappe.utils.xlsxutils import build_xlsx_response


class Exporter:
	def __init__(
		self,
		doctype,
		export_fields=None,
		export_data: bool = False,
		export_filters=None,
		export_page_length=None,
		file_type: str = "CSV",
	) -> None:
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
		self.exportable_fields = self.get_all_exportable_fields()
		self.fields = self.serialize_exportable_fields()
		self.add_header()

		if export_data:
			self.data = self.get_data_to_export()
		else:
			self.data = []
		self.add_data()

	def get_all_exportable_fields(self):
		child_table_fields = [df.fieldname for df in self.meta.fields if df.fieldtype in table_fieldtypes]

		meta = frappe.get_meta(self.doctype)
		exportable_fields = frappe._dict({})

		for key, fieldnames in self.export_fields.items():
			if key == self.doctype:
				# parent fields
				exportable_fields[key] = self.get_exportable_fields(key, fieldnames)

			elif key in child_table_fields:
				# child fields
				child_df = meta.get_field(key)
				child_doctype = child_df.options
				exportable_fields[key] = self.get_exportable_fields(child_doctype, fieldnames)

		return exportable_fields

	def serialize_exportable_fields(self):
		fields = []
		for key, exportable_fields in self.exportable_fields.items():
			for _df in exportable_fields:
				# make a copy of df dict to avoid reference mutation
				if isinstance(_df, frappe.core.doctype.docfield.docfield.DocField):
					df = _df.as_dict()
				else:
					df = _df.copy()

				df.is_child_table_field = key != self.doctype
				if df.is_child_table_field:
					df.child_table_df = self.meta.get_field(key)
				fields.append(df)
		return fields

	def get_exportable_fields(self, doctype, fieldnames):
		meta = frappe.get_meta(doctype)

		def is_exportable(df):
			return df and df.fieldtype not in (display_fieldtypes + no_value_fields)

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

		fields = [meta.get_field(fieldname) for fieldname in fieldnames]
		fields = [df for df in fields if is_exportable(df)]

		if "name" in fieldnames:
			fields = [name_field, *fields]

		return fields or []

	def get_data_to_export(self):
		frappe.permissions.can_export(self.doctype, raise_exception=True)

		table_fields = [f for f in self.exportable_fields if f != self.doctype]
		data = self.get_data_as_docs()

		for doc in data:
			rows = []
			rows = self.add_data_row(self.doctype, None, doc, rows, 0)
			if table_fields:
				# add child table data
				for f in table_fields:
					for i, child_row in enumerate(doc.get(f, [])):
						table_df = self.meta.get_field(f)
						child_doctype = table_df.options
						rows = self.add_data_row(child_doctype, child_row.parentfield, child_row, rows, i)

			yield from rows

	def add_data_row(self, doctype, parentfield, doc, rows, row_idx):
		if len(rows) < row_idx + 1:
			rows.append([""] * len(self.fields))

		row = rows[row_idx]

		for i, df in enumerate(self.fields):
			if df.parent == doctype:
				if df.is_child_table_field and df.child_table_df.fieldname != parentfield:
					continue
				value = doc.get(df.fieldname, None)

				if df.fieldtype == "Duration":
					value = format_duration(flt(value), df.hide_days)

				if df.fieldtype == "Text Editor" and value:
					value = frappe.core.utils.html2text(value)
				row[i] = value
		return rows

	def get_data_as_docs(self):
		def format_column_name(df) -> str:
			return f"`tab{df.parent}`.`{df.fieldname}`"

		filters = self.export_filters

		if self.meta.is_nested_set():
			order_by = f"`tab{self.doctype}`.`lft` ASC"
		else:
			order_by = f"`tab{self.doctype}`.`creation` DESC"

		parent_fields = [format_column_name(df) for df in self.fields if df.parent == self.doctype]
		parent_data = frappe.db.get_list(
			self.doctype,
			filters=filters,
			fields=["name", *parent_fields],
			limit_page_length=self.export_page_length,
			order_by=order_by,
			as_list=0,
		)
		parent_names = [p.name for p in parent_data]

		child_data = {}
		for key in self.exportable_fields:
			if key == self.doctype:
				continue
			child_table_df = self.meta.get_field(key)
			child_table_doctype = child_table_df.options
			child_fields = [
				"name",
				"idx",
				"parent",
				"parentfield",
				*list({format_column_name(df) for df in self.fields if df.parent == child_table_doctype}),
			]
			data = frappe.get_all(
				child_table_doctype,
				filters={
					"parent": ("in", parent_names),
					"parentfield": child_table_df.fieldname,
					"parenttype": self.doctype,
				},
				fields=child_fields,
				order_by="idx asc",
				as_list=0,
			)
			child_data[key] = data

		# Group children data by parent name
		grouped_children_data = self.group_children_data_by_parent(child_data)
		for doc in parent_data:
			related_children_docs = grouped_children_data.get(str(doc.name), {})
			yield {**doc, **related_children_docs}

	def add_header(self) -> None:
		header = []
		for df in self.fields:
			is_parent = not df.is_child_table_field
			if is_parent:
				label = _(df.label or df.fieldname)
			else:
				label = f"{_(df.label or df.fieldname)} ({_(df.child_table_df.label or df.child_table_df.fieldname)})"

			if label in header:
				# this label is already in the header,
				# which means two fields with the same label
				# add the fieldname to avoid clash
				if is_parent:
					label = f"{df.fieldname}"
				else:
					label = f"{df.child_table_df.fieldname}.{df.fieldname}"

			header.append(label)

		self.csv_array.append(header)

	def add_data(self) -> None:
		self.csv_array += self.data

	def get_csv_array(self):
		return self.csv_array

	def get_csv_array_for_export(self):
		csv_array = self.csv_array

		if not self.data:
			# add 2 empty rows
			csv_array += [[]] * 2

		return csv_array

	def build_response(self) -> None:
		if self.file_type == "CSV":
			build_csv_response(self.get_csv_array_for_export(), _(self.doctype))
		elif self.file_type == "Excel":
			build_xlsx_response(self.get_csv_array_for_export(), _(self.doctype))

	def group_children_data_by_parent(self, children_data: dict[str, list]):
		return groupby_metric(children_data, key="parent")
