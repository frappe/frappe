# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import re
from functools import lru_cache
from io import BytesIO

import openpyxl
import xlrd
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

import frappe
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)

DEFAULT_FONT_COLOR = "FF000000"  # Black
DEFAULT_BG_COLOR = "FFFFFFFF"  # White


def get_excel_date_format():
	date_format = frappe.get_system_settings("date_format")
	time_format = frappe.get_system_settings("time_format")

	# Excel-compatible format
	date_format = date_format.replace("mm", "MM")

	return date_format, time_format


# return xlsx file object
def make_xlsx(data, sheet_name, wb=None, column_widths=None):
	column_widths = column_widths or []
	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.create_sheet(sheet_name_sanitized, 0)

	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.column_dimensions[get_column_letter(i + 1)].width = column_width

	row1 = ws.row_dimensions[1]
	row1.font = Font(name="Calibri", bold=True)

	date_format, time_format = get_excel_date_format()
	cell_styling_in_export = frappe.flags.cell_styling_in_export

	for row in data:
		clean_row = []
		for item in row:
			cell_style = None

			# Check for cell styling info
			if cell_styling_in_export and isinstance(item, dict) and "value" in item:
				cell_style = item.get("style")
				item = item["value"]

			if isinstance(item, str) and (sheet_name not in ["Data Import Template", "Data Export"]):
				value = handle_html(item)
			else:
				value = item

			if isinstance(value, str) and next(ILLEGAL_CHARACTERS_RE.finditer(value), None):
				# Remove illegal characters from the string
				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			if isinstance(value, datetime.date | datetime.datetime):
				number_format = date_format
				if isinstance(value, datetime.datetime):
					number_format = f"{date_format} {time_format}"
				cell.number_format = number_format

			# Apply cell styles if any
			if cell_style:
				cs = cell_style  # alias
				font_kwargs = {"name": "Calibri"}

				# family
				if font_family := cs.get("font-family"):
					font_kwargs["name"] = font_family

				# color
				if color := cs.get("color"):
					font_kwargs["color"] = hex_to_argb(color, bg=True)

				# background color
				if bg_color := cs.get("background"):
					cell.fill = PatternFill(fill_type="solid", start_color=hex_to_argb(bg_color))

				# weight/style
				for s in ("bold", "italic", "strike"):
					font_kwargs[s] = bool(cs.get(s))

				if cs.get("underline"):
					font_kwargs["underline"] = "single"

				cell.font = Font(**font_kwargs)

			clean_row.append(cell)

		ws.append(clean_row)

	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	return xlsx_file


def handle_html(data):
	from frappe.core.utils import html2text

	# return if no html tags found
	data = frappe.as_unicode(data)

	if "<" not in data or ">" not in data:
		return data

	h = unescape_html(data or "")

	try:
		value = html2text(h, strip_links=True, wrap=False)
	except Exception:
		# unable to parse html, send it raw
		return data

	value = ", ".join(value.split("  \n"))
	value = " ".join(value.split("\n"))
	return ", ".join(value.split("# "))


def read_xlsx_file_from_attached_file(file_url=None, fcontent=None, filepath=None):
	if file_url:
		_file = frappe.get_doc("File", {"file_url": file_url})
		filename = _file.get_full_path()
	elif fcontent:
		filename = BytesIO(fcontent)
	elif filepath:
		filename = filepath
	else:
		return

	rows = []
	wb1 = load_workbook(filename=filename, data_only=True)
	ws1 = wb1.active
	for row in ws1.iter_rows():
		rows.append([cell.value for cell in row])
	return rows


def read_xls_file_from_attached_file(content):
	book = xlrd.open_workbook(file_contents=content)
	sheets = book.sheets()
	sheet = sheets[0]
	return [sheet.row_values(i) for i in range(sheet.nrows)]


def build_xlsx_response(data, filename):
	from frappe.desk.utils import provide_binary_file

	provide_binary_file(filename, "xlsx", make_xlsx(data, filename).getvalue())


@lru_cache(maxsize=128)
def hex_to_argb(color: str, bg: bool = False) -> str:
	"""
	Convert a CSS-style hex color to openpyxl ARGB ("AARRGGBB").

	Accepted inputs:
	- "#RGB"       -> expands to "FFRRGGBB"
	- "#RRGGBB"    -> converts to "FFRRGGBB"
	- "#RRGGBBAA"  -> converts RGBA to "AARRGGBB"

	"""
	default_color = DEFAULT_BG_COLOR if bg else DEFAULT_FONT_COLOR

	if not isinstance(color, str):
		return default_color

	s = color.strip()
	if not s.startswith("#"):
		return default_color

	hex_part = s[1:]

	if not hex_part or any(ch not in "0123456789abcdefABCDEF" for ch in hex_part):
		return default_color

	n = len(hex_part)

	if n == 3:
		r, g, b = hex_part
		rgb = (r + r + g + g + b + b).upper()
		return "FF" + rgb
	elif n == 6:
		return "FF" + hex_part.upper()
	elif n == 8:
		h = hex_part.upper()
		return h[6:8] + h[0:6]

	return DEFAULT_FONT_COLOR
