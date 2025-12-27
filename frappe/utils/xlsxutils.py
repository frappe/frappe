# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import re
from functools import lru_cache
from io import BytesIO
from typing import Any, Literal

import openpyxl
import xlrd
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

import frappe
from frappe.utils import cint
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)


def get_excel_date_format():
	date_format = frappe.get_system_settings("date_format")
	time_format = frappe.get_system_settings("time_format")

	# Excel-compatible format
	date_format = date_format.replace("mm", "MM")

	return date_format, time_format


def _build_number_format_parts(thousands_sep: str, decimal_sep: str, precision: int = 0) -> tuple[str, str]:
	integer_part = "#,##0" if thousands_sep else "#0"
	decimal_part = (decimal_sep + "0" * precision) if precision > 0 else ""

	return integer_part, decimal_part


def _get_currency_symbol_info(currency: str | None) -> tuple[str, bool]:
	if not currency or frappe.defaults.get_global_default("hide_currency_symbol") == "Yes":
		return "", False

	currency_symbol = frappe.db.get_value("Currency", currency, "symbol", cache=True) or currency
	symbol_on_right = frappe.db.get_value("Currency", currency, "symbol_on_right", cache=True) or False

	return frappe._(currency_symbol), symbol_on_right


def _apply_currency_symbol(
	format_string: str, currency_symbol: str | None = None, symbol_on_right: bool = False
) -> str:
	if not currency_symbol:
		return format_string

	return (
		f'{format_string}" {currency_symbol}"' if symbol_on_right else f'"{currency_symbol} "{format_string}'
	)


@lru_cache(maxsize=128)
def get_excel_number_format(
	fieldtype: Literal["Currency", "Int", "Float", "Percent"], currency: str | None = None
) -> str:
	"""
	Get Excel number format string based on system settings and field type.

	Args:
		fieldtype: The field type.
		currency: Currency code for Currency fields

	Returns:
		str: Excel number format string compatible with openpyxl

	Examples:
		- get_excel_number_format("Currency", "USD") >>> '"$"#,##0.00'
		- get_excel_number_format("Int") >>> '#,##0'
		- get_excel_number_format("Float") >>> '#,##0.000'
		- get_excel_number_format("Percent") >>> '0.00%'
	"""
	from frappe.locale import get_number_format

	number_format = get_number_format()
	thousands_sep = number_format.thousands_separator
	decimal_sep = number_format.decimal_separator
	precision = number_format.precision

	if fieldtype == "Currency":
		precision = cint(frappe.db.get_default("currency_precision")) or precision
		integer_part, decimal_part = _build_number_format_parts(thousands_sep, decimal_sep, precision)
		format_string = f"{integer_part}{decimal_part}"

		# Apply currency symbol if provided and not hidden
		currency_symbol, symbol_on_right = _get_currency_symbol_info(currency)
		return _apply_currency_symbol(format_string, currency_symbol, symbol_on_right)

	elif fieldtype == "Int":
		return "#,##0" if thousands_sep else "#0"

	elif fieldtype == "Float":
		precision = cint(frappe.db.get_default("float_precision")) or precision
		integer_part, decimal_part = _build_number_format_parts(thousands_sep, decimal_sep, precision)
		return f"{integer_part}{decimal_part}"

	elif fieldtype == "Percent":
		decimal_part = ("." + "0" * precision) if precision > 0 else ""
		return f"0{decimal_part}%"

	return "General"


# return xlsx file object
def make_xlsx(
	data: list[list[Any]],
	sheet_name: str,
	wb: openpyxl.Workbook | None = None,
	column_widths: list[int] | None = None,
	header_index: int = 0,
	has_filters: bool = False,
) -> BytesIO:
	"""
	Create an Excel file with the given data and formatting options.

	Args:
		data: List of rows, where each row is a list of cell values
		sheet_name: Name of the Excel sheet
		wb: Existing workbook to add sheet to. If None, creates new workbook
		column_widths: List of column widths in Excel units. If None, auto-sized
		header_index: Row index (0-based) that should be formatted as header making it bold
		has_filters: If True, applies bold formatting to the first column of filter rows

	Returns:
		BytesIO: object containing the Excel file data
	"""
	column_widths = column_widths or []
	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.create_sheet(sheet_name_sanitized, 0)

	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.column_dimensions[get_column_letter(i + 1)].width = column_width

	date_format, time_format = get_excel_date_format()
	bold_font = Font(name="Calibri", bold=True)

	for row_idx, row in enumerate(data):
		clean_row = []
		is_header_row = row_idx == header_index
		is_filter_row = has_filters and row_idx < header_index

		for col_idx, item in enumerate(row):
			if isinstance(item, str) and (sheet_name not in ["Data Import Template", "Data Export"]):
				value = handle_html(item)
			else:
				value = item

			if isinstance(item, str) and next(ILLEGAL_CHARACTERS_RE.finditer(value), None):
				# Remove illegal characters from the string
				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			if isinstance(value, datetime.date | datetime.datetime):
				number_format = date_format
				if isinstance(value, datetime.datetime):
					number_format = f"{date_format} {time_format}"
				cell.number_format = number_format

			# Apply bold font for header row or first column of filter rows
			if is_header_row or (is_filter_row and col_idx == 0):
				cell.font = bold_font

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
def hex_to_argb(color: str) -> str:
	"""
	Convert a CSS-style hex color to openpyxl ARGB ("AARRGGBB").

	Accepted inputs:
	- "#RGB"       -> expands to "FFRRGGBB"
	- "#RRGGBB"    -> converts to "FFRRGGBB"
	- "#RRGGBBAA"  -> converts RGBA to "AARRGGBB"

	"""
	color = color.strip()

	hex_part = color[1:]

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
