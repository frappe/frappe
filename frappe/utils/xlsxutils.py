# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import re
from collections.abc import Callable
from functools import lru_cache
from io import BytesIO
from typing import Any, ClassVar, Literal

import openpyxl
import xlrd
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)


# TODO: add docs and examples for XLSXStyleBuilder
# TODO: when registering make user friendly for Developers (common methods)
# TODO: give default styles
# TODO: User can update default styles
# TODO: can give range of cells to style
class XLSXStyleBuilder:
	# Mapping of style property names to their openpyxl classes
	_STYLE_CLASSES: ClassVar[dict] = {
		"font": Font,
		"fill": PatternFill,
		"alignment": Alignment,
		"border": Border,
	}

	def __init__(self):
		self.config = frappe._dict(
			column_styles={},
			row_styles={},
			cell_styles={},
			conditional_styles=[],
		)
		self.styles = frappe._dict()

	def register_style(self, name: str, **kwargs):
		"""
		Register a named style for reuse across multiple cells/rows/columns.

		Args:
			name: Unique name for this style
			font: Font configuration (dict or Font object)
			fill: Fill configuration (dict or PatternFill object)
			number_format: Excel number format string
			alignment: Alignment configuration (dict or Alignment object)
			border: Border configuration (dict or Border object)
		"""
		style = frappe._dict()

		# Handle number format
		if number_format := kwargs.get("number_format"):
			style.number_format = number_format

		# Handle style objects with automatic instantiation
		for prop_name, style_class in self._STYLE_CLASSES.items():
			if config := kwargs.get(prop_name):
				style[prop_name] = style_class(**config) if isinstance(config, dict) else config

		self.styles[name] = style
		return self

	def _validate_style_exists(self, style_name: str):
		if style_name not in self.styles:
			frappe.throw(
				_("Style '{0}' not registered. Register it first using register_style().").format(style_name),
				title=_("Style Not Registered"),
			)

	def style_column(self, col_idx: int, style_name: str):
		self._validate_style_exists(style_name)
		self.config.column_styles[col_idx] = self.styles[style_name]
		return self

	def style_row(self, row_idx: int, style_name: str):
		self._validate_style_exists(style_name)
		self.config.row_styles[row_idx] = self.styles[style_name]
		return self

	def style_cell(self, row_idx: int, col_idx: int, style_name: str):
		self._validate_style_exists(style_name)
		self.config.cell_styles[(row_idx, col_idx)] = self.styles[style_name]
		return self

	def add_conditional_style(self, condition: Callable[[int, int, Any], bool], style_name: str):
		self._validate_style_exists(style_name)
		self.config.conditional_styles.append({"condition": condition, "style": self.styles[style_name]})
		return self

	def build(self) -> frappe._dict:
		return self.config


### Excel Formatting Utils ###
def get_excel_date_format():
	date_format = frappe.get_system_settings("date_format")
	time_format = frappe.get_system_settings("time_format")

	# Excel-compatible format
	date_format = date_format.replace("mm", "MM")

	return date_format, time_format


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

	if fieldtype == "Int":
		return "#,##0" if thousands_sep else "#0"

	elif fieldtype == "Currency":
		precision = cint(frappe.db.get_default("currency_precision")) or precision
		format = _build_number_format(thousands_sep, decimal_sep, precision)

		currency_symbol, symbol_on_right = _get_currency_symbol_info(currency)
		return _get_currency_format(format, currency_symbol, symbol_on_right)

	elif fieldtype in ("Float", "Percent"):
		precision = cint(frappe.db.get_default("float_precision")) or precision
		format = _build_number_format(thousands_sep, decimal_sep, precision)

		return f'{format}"%" ' if fieldtype == "Percent" else format

	return "General"


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


def get_default_xlsx_styles(data) -> dict:
	# add default styles here
	# like indentation, bold headers, filters etc.
	pass


### Excel Creation Utils ###
def make_xlsx(
	data: list[list[Any]],
	sheet_name: str,
	wb: openpyxl.Workbook | None = None,
	column_widths: list[int] | None = None,
	header_index: int = 0,
	has_filters: bool = False,
	styles: dict | None = None,
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
		styles: Configuration for cell/row/column styles
			- Should contain: column_styles, row_styles, cell_styles, conditional_styles

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


### HELPERS ###
def _build_number_format(thousands_sep: str, decimal_sep: str, precision: int = 0) -> str:
	integer_part = "#,##0" if thousands_sep else "#0"
	decimal_part = (decimal_sep + "0" * precision) if precision > 0 else ""

	return f"{integer_part}{decimal_part}"


def _get_currency_symbol_info(currency: str | None) -> tuple[str, bool]:
	if not currency or frappe.db.get_default("hide_currency_symbol") == "Yes":
		return "", False

	symbol, on_right = frappe.db.get_value("Currency", currency, ["symbol", "symbol_on_right"], cache=True)

	return frappe._(symbol or currency), bool(on_right)


def _get_currency_format(
	format_string: str,
	currency_symbol: str | None = None,
	symbol_on_right: bool = False,
) -> str:
	if not currency_symbol:
		return format_string

	if symbol_on_right:
		return f'{format_string}" {currency_symbol}";-{format_string}" {currency_symbol}"'

	return f'"{currency_symbol} "{format_string};"{currency_symbol} "-{format_string}'
