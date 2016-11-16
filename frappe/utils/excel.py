# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import os, frappe
import re
from frappe import _

import xlsxwriter
from frappe.utils import cint, strip_html, get_site_name
from bs4 import BeautifulSoup

def get_excel(doctype=None, name=None, print_format=None, style=None):
	doc = frappe.get_doc(doctype, name)
	meta = frappe.get_meta(doctype)

	print_settings = frappe.db.get_singles_dict("Print Settings")
	# print print_settings

	if not frappe.flags.ignore_print_permissions:
		validate_print_permission(doc)

	if doc.meta.is_submittable:
		if doc.docstatus==0 and not print_settings.allow_print_for_draft:
			frappe.throw(_("Not allowed to print draft documents"), frappe.PermissionError)

		if doc.docstatus==2 and not print_settings.allow_print_for_cancelled:
			frappe.throw(_("Not allowed to print cancelled documents"), frappe.PermissionError)


	# create a new workbook with 1 worksheet
	fname = os.path.join("/tmp", "frappe-excel-{0}.xlsx".format(frappe.generate_hash()))
	workbook = xlsxwriter.Workbook(fname)
	cur_worksheet = workbook.add_worksheet()
	cur_worksheet.set_column('A:A', 30)
	cur_worksheet.set_column('B:B', 15)
	cur_worksheet.set_column('C:C', 15)
	cur_worksheet.set_column('D:D', 15)
	cur_worksheet.set_column('E:E', 15)
	cur_worksheet.set_column('F:F', 15)
	cur_worksheet.set_column('G:G', 15)
	cur_worksheet.set_column('H:H', 15)
	cur_worksheet.set_column('I:I', 15)

	starting_row = 3
	starting_col = 'A'
	output_sheet_header(doc, meta, cur_worksheet, starting_row, starting_col)
	workbook.close()

	return fname

def output_sheet_header(doc, meta, cur_worksheet, current_row, current_col):
	#check if we have a header
	# print os.getcwd()
	# print get_site_name()
	letter_head = get_letter_head(doc, None)
	matchObj = re.search(r'src="(.+)"', letter_head.content, re.I)
	letterhead_path = "%s%s" % ('pixel.local/public', matchObj.group(1))
	# print letterhead_path
	cur_cell_ref = "%s%d" % (current_col, current_row)
	cur_worksheet.insert_image(cur_cell_ref, letterhead_path)
	current_row = current_row + 12

	# output the sheet headers
	for df in meta.fields:
		if is_visible(df, doc) and has_value(df, doc):
			if df.fieldtype == 'Table':
				current_row = output_table(doc, meta, df, cur_worksheet, current_row)
				current_row = current_row + 2

			if df.fieldtype != 'Table':
				cur_ref_cell = "%s%d" % (current_col, current_row)
				cur_val_cell = "%s%d" % (chr(ord(current_col) + 1), current_row)
				cur_worksheet.write(cur_ref_cell, df.label)
				cur_worksheet.write(cur_val_cell, doc.get(df.fieldname))
				current_row = current_row + 1


def output_table(doc, meta, df, cur_worksheet, current_row):
	# mimick the pdf functionality
	df.rows = []
	df.start = 0
	df.end = None
	for i, row in enumerate(doc.get(df.fieldname)):
		if row.get("page_break"):
			# close the earlier row
			df.end = i

			# new page, with empty section and column
			page = [[[]]]
			layout.append(page)

			# continue the table in a new page
			df = copy.copy(df)
			df.start = i
			df.end = None
			page[-1][-1].append(df)

	# now lets mimick the print functionality for the rows
	table_meta = frappe.get_meta(df.options)
	data = doc.get(df.fieldname)[df.start:df.end]

	# starting with column
	start_col = 'A'
	if data:
		visible_columns = get_visible_columns(doc.get(df.fieldname), table_meta, df)
		col_ascii = 0
		current_row = current_row + 1
		for tdf in visible_columns:
			col_ref = chr(ord(start_col) + col_ascii)
			cur_cell_ref = "%s%d" % (col_ref, current_row)
			cur_worksheet.write(cur_cell_ref, tdf.label)
			col_ascii = col_ascii + 1

		for d in data:
			current_row = current_row + 1
			col_ascii = 0
			for tdf in visible_columns:
				col_ref = chr(ord(start_col) + col_ascii)
				cur_cell_ref = "%s%d" % (col_ref, current_row)
				cur_cell_value = print_value(tdf, d, table_meta, doc)
				cur_worksheet.write(cur_cell_ref, cur_cell_value)
				col_ascii = col_ascii + 1

	return current_row

def print_value(df, doc, meta, parent_doc=None):
	if df.fieldtype=="Check":
		# print 'Checkbox'
		return df.fieldname
	elif df.fieldtype=="Image":
		# print 'Image'
		return doc[doc.meta.get_field(df.fieldname).options]
	elif df.fieldtype in ("Attach", "Attach Image") and doc[df.fieldname] and (guess_mimetype(doc[df.fieldname])[0] or "").startswith("image/"):
		# print 'Attach Image'
		doc[df.fieldname]
	elif df.fieldtype=="HTML":
		# print 'HTML'
		return "some html -- more processing"
	else:
		# print 'something else'
		return doc.get_formatted(df.fieldname, doc, translated=True)


def get_visible_columns(data, table_meta, df):
	"""Returns list of visible columns based on print_hide and if all columns have value."""
	columns = []
	doc = data[0] or frappe.new_doc(df.options)
	def add_column(col_df):
		return is_visible(col_df, doc) \
			and column_has_value(data, col_df.get("fieldname"))

	if df.get("visible_columns"):
		# columns specified by column builder
		for col_df in df.get("visible_columns"):
			# load default docfield properties
			docfield = table_meta.get_field(col_df.get("fieldname"))
			if not docfield:
				continue
			newdf = docfield.as_dict().copy()
			newdf.update(col_df)
			if add_column(newdf):
				columns.append(newdf)
	else:
		for col_df in table_meta.fields:
			if add_column(col_df):
				columns.append(col_df)

	return columns


def column_has_value(data, fieldname):
	"""Check if at least one cell in column has non-zero and non-blank value"""
	has_value = False

	for row in data:
		value = row.get(fieldname)
		if value:
			if isinstance(value, basestring):
				if strip_html(value).strip():
					has_value = True
					break
			else:
				has_value = True
				break

	return has_value


def validate_print_permission(doc):
	if frappe.form_dict.get("key"):
		if frappe.form_dict.key == doc.get_signature():
			return

	for ptype in ("read", "print"):
		if (not frappe.has_permission(doc.doctype, ptype, doc)
			and not frappe.has_website_permission(doc.doctype, ptype, doc)):
			raise frappe.PermissionError(_("No {0} permission").format(ptype))


def has_value(df, doc):
	value = doc.get(df.fieldname)
	if value in (None, ""):
		return False

	elif isinstance(value, basestring) and not strip_html(value).strip():
		return False

	elif isinstance(value, list) and not len(value):
		return False

	return True


def is_visible(df, doc):
	"""Returns True if docfield is visible in print layout and does not have print_hide set."""
	if df.fieldtype in ("Section Break", "Column Break", "Button"):
		return False

	if hasattr(doc, "hide_in_print_layout"):
		if df.fieldname in doc.hide_in_print_layout:
			return False

	if df.permlevel > 0 and not doc.has_permlevel_access_to(df.fieldname, df):
		return False

	return not doc.is_print_hide(df.fieldname, df)


def get_letter_head(doc, no_letterhead):
	if no_letterhead:
		return {}
	if doc.get("letter_head"):
		return frappe.db.get_value("Letter Head", doc.letter_head, ["content", "footer"], as_dict=True)
	else:
		return frappe.db.get_value("Letter Head", {"is_default": 1}, ["content", "footer"], as_dict=True) or {}


