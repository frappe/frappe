# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, json, os
import frappe.permissions
from frappe.utils.datautils import UnicodeWriter
from frappe.utils import cstr, cint, flt

from frappe.core.page.data_import_tool.data_import_tool import data_keys

@frappe.whitelist()
def get_template(doctype=None, parent_doctype=None, all_doctypes="No", with_data="No"):
	all_doctypes = all_doctypes=="Yes"
	if not parent_doctype:
		parent_doctype = doctype

	column_start_end = {}

	if all_doctypes:
		doctype_parentfield = {}
		child_doctypes = []
		for df in frappe.get_meta(doctype).get_table_fields():
			child_doctypes.append(df.options)
			doctype_parentfield[df.options] = df.fieldname

	def add_main_header():
		w.writerow(['Data Import Template'])
		w.writerow([data_keys.main_table, doctype])

		if parent_doctype != doctype:
			w.writerow([data_keys.parent_table, parent_doctype])
		else:
			w.writerow([''])

		w.writerow([''])
		w.writerow(['Notes:'])
		w.writerow(['Please do not change the template headings.'])
		w.writerow(['First data column must be blank.'])
		w.writerow(['If you are uploading new records, leave the "name" (ID) column blank.'])
		w.writerow(['If you are uploading new records, "Naming Series" becomes mandatory, if present.'])
		w.writerow(['Only mandatory fields are necessary for new records. You can delete non-mandatory columns if you wish.'])
		w.writerow(['For updating, you can update only selective columns.'])
		w.writerow(['You can only upload upto 5000 records in one go. (may be less in some cases)'])
		if key == "parent":
			w.writerow(['"Parent" signifies the parent table in which this row must be added'])
			w.writerow(['If you are updating, please select "Overwrite" else existing rows will not be deleted.'])

	def build_field_columns(dt):
		meta = frappe.get_meta(dt)

		tablecolumns = filter(None,
			[(meta.get_field(f[0]) or None) for f in frappe.db.sql('desc `tab%s`' % dt)])

		tablecolumns.sort(lambda a, b: a.idx - b.idx)

		if dt==doctype:
			column_start_end[dt] = frappe._dict({"start": 0})
		else:
			column_start_end[dt] = frappe._dict({"start": len(columns)})

			append_field_column(frappe._dict({
				"fieldname": "name",
				"label": "ID",
				"fieldtype": "Data",
				"reqd": 1,
				"idx": 0,
				"info": "Leave blank for new records"
			}), True)

		for docfield in tablecolumns:
			append_field_column(docfield, True)

		# all non mandatory fields
		for docfield in tablecolumns:
			append_field_column(docfield, False)

		# append DocType name
		tablerow[column_start_end[dt].start + 1] = dt
		if dt!=doctype:
			tablerow[column_start_end[dt].start + 2] = doctype_parentfield[dt]

		column_start_end[dt].end = len(columns) + 1

	def append_field_column(docfield, mandatory):
		if docfield and ((mandatory and docfield.reqd) or not (mandatory or docfield.reqd)) \
			and (docfield.fieldname not in ('parenttype', 'trash_reason')) and not docfield.hidden:
			tablerow.append("")
			fieldrow.append(docfield.fieldname)
			labelrow.append(docfield.label)
			mandatoryrow.append(docfield.reqd and 'Yes' or 'No')
			typerow.append(docfield.fieldtype)
			inforow.append(getinforow(docfield))
			columns.append(docfield.fieldname)

	def append_empty_field_column():
		tablerow.append("~")
		fieldrow.append("~")
		labelrow.append("")
		mandatoryrow.append("")
		typerow.append("")
		inforow.append("")
		columns.append("")

	def getinforow(docfield):
		"""make info comment for options, links etc."""
		if docfield.fieldtype == 'Select':
			if not docfield.options:
				return ''
			elif docfield.options.startswith('link:'):
				return 'Valid %s' % docfield.options[5:]
			else:
				return 'One of: %s' % ', '.join(filter(None, docfield.options.split('\n')))
		elif docfield.fieldtype == 'Link':
			return 'Valid %s' % docfield.options
		elif docfield.fieldtype == 'Int':
			return 'Integer'
		elif docfield.fieldtype == "Check":
			return "0 or 1"
		elif hasattr(docfield, "info"):
			return docfield.info
		else:
			return ''

	def add_field_headings():
		w.writerow(tablerow)
		w.writerow(labelrow)
		w.writerow(fieldrow)
		w.writerow(mandatoryrow)
		w.writerow(typerow)
		w.writerow(inforow)
		w.writerow([data_keys.data_separator])

	def add_data():
		def add_data_row(row_group, dt, doc, rowidx):
			d = doc.copy()
			if all_doctypes:
				d.name = '"'+ d.name+'"'

			if len(row_group) < rowidx + 1:
				row_group.append([""] * (len(columns) + 1))
			row = row_group[rowidx]
			for i, c in enumerate(columns[column_start_end[dt].start:column_start_end[dt].end]):
				row[column_start_end[dt].start + i + 1] = d.get(c, "")

		if with_data=='Yes':
			frappe.permissions.can_export(parent_doctype, raise_exception=True)

			# get permitted data only
			data = frappe.get_list(doctype, fields=["*"], limit_page_length=None)
			for doc in data:
				# add main table
				row_group = []

				add_data_row(row_group, doctype, doc, 0)

				if all_doctypes:
					# add child tables
					for child_doctype in child_doctypes:
						for ci, child in enumerate(frappe.db.sql("""select * from `tab%s`
							where parent=%s order by idx""" % (child_doctype, "%s"), doc.name, as_dict=1)):
							add_data_row(row_group, child_doctype, child, ci)

				for row in row_group:
					w.writerow(row)

	w = UnicodeWriter()
	key = 'parent' if parent_doctype != doctype else 'name'

	add_main_header()

	w.writerow([''])
	tablerow = [data_keys.doctype, ""]
	labelrow = ["Column Labels:", "ID"]
	fieldrow = [data_keys.columns, key]
	mandatoryrow = ['Mandatory:', 'Yes']
	typerow = ['Type:', 'Data (text)']
	inforow = ['Info:', '']
	columns = [key]

	build_field_columns(doctype)
	if all_doctypes:
		for d in child_doctypes:
			append_empty_field_column()
			build_field_columns(d)

	add_field_headings()
	add_data()

	# write out response as a type csv
	frappe.response['result'] = cstr(w.getvalue())
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = doctype
