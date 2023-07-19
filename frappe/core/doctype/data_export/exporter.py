# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import csv
import os
import re

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model.utils import is_virtual_doctype
from frappe.utils import cint, cstr, format_datetime, format_duration, formatdate, parse_json
from frappe.utils.csvutils import UnicodeWriter

reflags = {"I": re.I, "L": re.L, "M": re.M, "U": re.U, "S": re.S, "X": re.X, "D": re.DEBUG}


def get_data_keys():
	return frappe._dict(
		{
			"data_separator": _("Start entering data below this line"),
			"main_table": _("Table") + ":",
			"parent_table": _("Parent Table") + ":",
			"columns": _("Column Name") + ":",
			"doctype": _("DocType") + ":",
		}
	)


@frappe.whitelist()
def export_data(
	doctype=None,
	parent_doctype=None,
	all_doctypes=True,
	with_data=False,
	select_columns=None,
	file_type="CSV",
	template=False,
	filters=None,
):
	_doctype = doctype
	if isinstance(_doctype, list):
		_doctype = _doctype[0]
	make_access_log(
		doctype=_doctype,
		file_type=file_type,
		columns=select_columns,
		filters=filters,
		method=parent_doctype,
	)
	exporter = DataExporter(
		doctype=doctype,
		parent_doctype=parent_doctype,
		all_doctypes=all_doctypes,
		with_data=with_data,
		select_columns=select_columns,
		file_type=file_type,
		template=template,
		filters=filters,
	)
	exporter.build_response()


class DataExporter:
	def __init__(
		self,
		doctype=None,
		parent_doctype=None,
		all_doctypes=True,
		with_data=False,
		select_columns=None,
		file_type="CSV",
		template=False,
		filters=None,
	):
		self.doctype = doctype
		self.parent_doctype = parent_doctype
		self.all_doctypes = all_doctypes
		self.with_data = cint(with_data)
		self.select_columns = select_columns
		self.file_type = file_type
		self.template = template
		self.filters = filters
		self.data_keys = get_data_keys()

		self.prepare_args()

	def prepare_args(self):
		if self.select_columns:
			self.select_columns = parse_json(self.select_columns)
		if self.filters:
			self.filters = parse_json(self.filters)

		self.docs_to_export = {}
		if self.doctype:
			if isinstance(self.doctype, str):
				self.doctype = [self.doctype]

			if len(self.doctype) > 1:
				self.docs_to_export = self.doctype[1]
			self.doctype = self.doctype[0]

		if not self.parent_doctype:
			self.parent_doctype = self.doctype

		self.column_start_end = {}

		if self.all_doctypes:
			self.child_doctypes = []
			for df in frappe.get_meta(self.doctype).get_table_fields():
				self.child_doctypes.append(dict(doctype=df.options, parentfield=df.fieldname))

	def build_response(self):
		self.writer = UnicodeWriter()
		self.name_field = "parent" if self.parent_doctype != self.doctype else "name"

		if self.template:
			self.add_main_header()

		self.writer.writerow([""])
		self.tablerow = [self.data_keys.doctype]
		self.labelrow = [_("Column Labels:")]
		self.fieldrow = [self.data_keys.columns]
		self.mandatoryrow = [_("Mandatory:")]
		self.typerow = [_("Type:")]
		self.inforow = [_("Info:")]
		self.columns = []

		self.build_field_columns(self.doctype)

		if self.all_doctypes:
			for d in self.child_doctypes:
				self.append_empty_field_column()
				if (
					self.select_columns and self.select_columns.get(d["doctype"], None)
				) or not self.select_columns:
					# if atleast one column is selected for this doctype
					self.build_field_columns(d["doctype"], d["parentfield"])

		self.add_field_headings()
		self.add_data()
		if self.with_data and not self.data:
			frappe.respond_as_web_page(
				_("No Data"), _("There is no data to be exported"), indicator_color="orange"
			)

		if self.file_type == "Excel":
			self.build_response_as_excel()
		else:
			# write out response as a type csv
			frappe.response["result"] = cstr(self.writer.getvalue())
			frappe.response["type"] = "csv"
			frappe.response["doctype"] = self.doctype

	def add_main_header(self):
		self.writer.writerow([_("Data Import Template")])
		self.writer.writerow([self.data_keys.main_table, self.doctype])

		if self.parent_doctype != self.doctype:
			self.writer.writerow([self.data_keys.parent_table, self.parent_doctype])
		else:
			self.writer.writerow([""])

		self.writer.writerow([""])
		self.writer.writerow([_("Notes:")])
		self.writer.writerow([_("Please do not change the template headings.")])
		self.writer.writerow([_("First data column must be blank.")])
		self.writer.writerow(
			[_('If you are uploading new records, leave the "name" (ID) column blank.')]
		)
		self.writer.writerow(
			[_('If you are uploading new records, "Naming Series" becomes mandatory, if present.')]
		)
		self.writer.writerow(
			[
				_(
					"Only mandatory fields are necessary for new records. You can delete non-mandatory columns if you wish."
				)
			]
		)
		self.writer.writerow([_("For updating, you can update only selective columns.")])
		self.writer.writerow(
			[_("You can only upload upto 5000 records in one go. (may be less in some cases)")]
		)
		if self.name_field == "parent":
			self.writer.writerow([_('"Parent" signifies the parent table in which this row must be added')])
			self.writer.writerow(
				[_('If you are updating, please select "Overwrite" else existing rows will not be deleted.')]
			)

	def build_field_columns(self, dt, parentfield=None):
		meta = frappe.get_meta(dt)

		# build list of valid docfields
		tablecolumns = []
		table_name = "tab" + dt
		for f in frappe.db.get_table_columns_description(table_name):
			field = meta.get_field(f.name)
			if field and (
				(self.select_columns and f.name in self.select_columns[dt]) or not self.select_columns
			):
				tablecolumns.append(field)

		tablecolumns.sort(key=lambda a: int(a.idx))

		_column_start_end = frappe._dict(start=0)

		if dt == self.doctype:
			if (meta.get("autoname") and meta.get("autoname").lower() == "prompt") or (self.with_data):
				self._append_name_column()

			# if importing only child table for new record, add parent field
			if meta.get("istable") and not self.with_data:
				self.append_field_column(
					frappe._dict(
						{
							"fieldname": "parent",
							"parent": "",
							"label": "Parent",
							"fieldtype": "Data",
							"reqd": 1,
							"info": _("Parent is the name of the document to which the data will get added to."),
						}
					),
					True,
				)

			_column_start_end = frappe._dict(start=0)
		else:
			_column_start_end = frappe._dict(start=len(self.columns))

			if self.with_data:
				self._append_name_column(dt)

		for docfield in tablecolumns:
			self.append_field_column(docfield, True)

		# all non mandatory fields
		for docfield in tablecolumns:
			self.append_field_column(docfield, False)

		# if there is one column, add a blank column (?)
		if len(self.columns) - _column_start_end.start == 1:
			self.append_empty_field_column()

		# append DocType name
		self.tablerow[_column_start_end.start + 1] = dt

		if parentfield:
			self.tablerow[_column_start_end.start + 2] = parentfield

		_column_start_end.end = len(self.columns) + 1

		self.column_start_end[(dt, parentfield)] = _column_start_end

	def append_field_column(self, docfield, for_mandatory):
		if not docfield:
			return
		if for_mandatory and not docfield.reqd:
			return
		if not for_mandatory and docfield.reqd:
			return
		if docfield.fieldname in ("parenttype", "trash_reason"):
			return
		if docfield.hidden:
			return
		if (
			self.select_columns
			and docfield.fieldname not in self.select_columns.get(docfield.parent, [])
			and docfield.fieldname != "name"
		):
			return

		self.tablerow.append("")
		self.fieldrow.append(docfield.fieldname)
		self.labelrow.append(_(docfield.label))
		self.mandatoryrow.append(docfield.reqd and "Yes" or "No")
		self.typerow.append(docfield.fieldtype)
		self.inforow.append(self.getinforow(docfield))
		self.columns.append(docfield.fieldname)

	def append_empty_field_column(self):
		self.tablerow.append("~")
		self.fieldrow.append("~")
		self.labelrow.append("")
		self.mandatoryrow.append("")
		self.typerow.append("")
		self.inforow.append("")
		self.columns.append("")

	@staticmethod
	def getinforow(docfield):
		"""make info comment for options, links etc."""
		if docfield.fieldtype == "Select":
			if not docfield.options:
				return ""
			else:
				return _("One of") + ": %s" % ", ".join(filter(None, docfield.options.split("\n")))
		elif docfield.fieldtype == "Link":
			return "Valid %s" % docfield.options
		elif docfield.fieldtype == "Int":
			return "Integer"
		elif docfield.fieldtype == "Check":
			return "0 or 1"
		elif docfield.fieldtype in ["Date", "Datetime"]:
			return cstr(frappe.defaults.get_defaults().date_format)
		elif hasattr(docfield, "info"):
			return docfield.info
		else:
			return ""

	def add_field_headings(self):
		self.writer.writerow(self.tablerow)
		self.writer.writerow(self.labelrow)
		self.writer.writerow(self.fieldrow)
		self.writer.writerow(self.mandatoryrow)
		self.writer.writerow(self.typerow)
		self.writer.writerow(self.inforow)
		if self.template:
			self.writer.writerow([self.data_keys.data_separator])

	def add_data(self):
		from frappe.query_builder import DocType

		if self.template and not self.with_data:
			return

		frappe.permissions.can_export(self.parent_doctype, raise_exception=True)

		# sort nested set doctypes by `lft asc`
		order_by = None
		table_columns = frappe.db.get_table_columns(self.parent_doctype)
		if "lft" in table_columns and "rgt" in table_columns:
			order_by = f"`tab{self.parent_doctype}`.`lft` asc"
		# get permitted data only
		self.data = frappe.get_list(
			self.doctype, fields=["*"], filters=self.filters, limit_page_length=None, order_by=order_by
		)

		for doc in self.data:
			op = self.docs_to_export.get("op")
			names = self.docs_to_export.get("name")

			if names and op:
				if op == "=" and doc.name not in names:
					continue
				elif op == "!=" and doc.name in names:
					continue
			elif names:
				try:
					sflags = self.docs_to_export.get("flags", "I,U").upper()
					flags = 0
					for a in re.split(r"\W+", sflags):
						flags = flags | reflags.get(a, 0)

					c = re.compile(names, flags)
					m = c.match(doc.name)
					if not m:
						continue
				except Exception:
					if doc.name not in names:
						continue
			# add main table
			rows = []

			self.add_data_row(rows, self.doctype, None, doc, 0)

			if self.all_doctypes:
				# add child tables
				for c in self.child_doctypes:
					if is_virtual_doctype(c["doctype"]):
						continue
					child_doctype_table = DocType(c["doctype"])
					data_row = (
						frappe.qb.from_(child_doctype_table)
						.select("*")
						.where(child_doctype_table.parent == doc.name)
						.where(child_doctype_table.parentfield == c["parentfield"])
						.orderby(child_doctype_table.idx)
					)
					for ci, child in enumerate(data_row.run(as_dict=True)):
						self.add_data_row(rows, c["doctype"], c["parentfield"], child, ci)

			for row in rows:
				self.writer.writerow(row)

	def add_data_row(self, rows, dt, parentfield, doc, rowidx):
		d = doc.copy()
		meta = frappe.get_meta(dt)
		if self.all_doctypes:
			d.name = f'"{d.name}"'

		if len(rows) < rowidx + 1:
			rows.append([""] * (len(self.columns) + 1))
		row = rows[rowidx]

		_column_start_end = self.column_start_end.get((dt, parentfield))

		if _column_start_end:
			for i, c in enumerate(self.columns[_column_start_end.start : _column_start_end.end]):
				df = meta.get_field(c)
				fieldtype = df.fieldtype if df else "Data"
				value = d.get(c, "")
				if value:
					if fieldtype == "Date":
						value = formatdate(value)
					elif fieldtype == "Datetime":
						value = format_datetime(value)
					elif fieldtype == "Duration":
						value = format_duration(value, df.hide_days)

				row[_column_start_end.start + i + 1] = value

	def build_response_as_excel(self):
		filename = frappe.generate_hash(length=10)
		with open(filename, "wb") as f:
			f.write(cstr(self.writer.getvalue()).encode("utf-8"))
		f = open(filename)
		reader = csv.reader(f)

		from frappe.utils.xlsxutils import make_xlsx

		xlsx_file = make_xlsx(reader, "Data Import Template" if self.template else "Data Export")

		f.close()
		os.remove(filename)

		# write out response as a xlsx type
		frappe.response["filename"] = _(self.doctype) + ".xlsx"
		frappe.response["filecontent"] = xlsx_file.getvalue()
		frappe.response["type"] = "binary"

	def _append_name_column(self, dt=None):
		self.append_field_column(
			frappe._dict(
				{
					"fieldname": "name" if dt else self.name_field,
					"parent": dt or "",
					"label": "ID",
					"fieldtype": "Data",
					"reqd": 1,
				}
			),
			True,
		)
