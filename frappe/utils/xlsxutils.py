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


# TODO: Date and Time formats not working properly need to fix
# TODO: add docs and examples for XLSXStyleBuilder
# TODO: Handle Currency formatting
# TODO: Check for border styles


class XLSXStyleBuilder:
	# Mapping of style property names to their openpyxl classes
	STYLE_CLASSES: ClassVar[dict] = {
		"font": Font,
		"fill": PatternFill,
		"alignment": Alignment,
		"border": Border,
	}

	FIELDTYPE_STYLES: ClassVar[dict] = {
		"Int": "int_format",
		"Float": "float_format",
		"Percent": "percent_format",
		"Date": "date_format",
		"Time": "time_format",
		"Datetime": "datetime_format",
		"Currency": "default_currency_format",
	}

	def __init__(self, **kwargs):
		self.settings = kwargs or {}

		self.styles = {}

		self.config = {
			"column_styles": {},
			"row_styles": {},
			"cell_styles": {},
		}

		self.default_styles = {
			"header": {
				"font": {"bold": True, "size": 12},
			},
			"total_row": {
				"font": {"bold": True},
			},
			"filter_label": {
				"font": {"bold": True},
			},
		}

		self._register_default_styles()

	def _register_default_styles(self):
		for name, style in self.default_styles.items():
			self.register_style(name, **style)

		self._register_indent_styles()
		self._register_number_formats()

	def _register_indent_styles(self):
		max_indent = self.settings.get("max_indent_level") or 2
		pt = self.settings.get("indent_pt") or 2

		for indent in range(max_indent + 1):
			self.register_style(self.indent_key(indent), **self.get_indent_style(indent, pt))

	def _register_number_formats(self):
		map = {
			"int_format": self.get_number_format("Int"),
			"float_format": self.get_number_format("Float"),
			"percent_format": self.get_number_format("Percent"),
			"date_format": self.get_date_format(),
			"time_format": self.get_time_format(),
			"datetime_format": self.get_datetime_format(),
			"default_currency_format": self.get_number_format("Currency", self.settings.get("currency")),
		}

		for style_name, format in map.items():
			self.register_style(style_name, number_format=format)

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
		for prop_name, style_class in self.STYLE_CLASSES.items():
			if config := kwargs.get(prop_name):
				style[prop_name] = style_class(**config) if isinstance(config, dict) else config

		self.styles[name] = style

	def register_currency_format(self, currency: str, style_name: str | None = None) -> str:
		style_name = style_name or f"{currency.lower()}_currency_format"
		number_format = self.get_number_format("Currency", currency)

		self.register_style(style_name, number_format=number_format)

		return style_name

	def style_column(self, col_idx: int, style_name: str):
		self.config["column_styles"][col_idx] = self.styles[style_name]

	def style_row(self, row_idx: int, style_name: str):
		self.config["row_styles"][row_idx] = self.styles[style_name]

	def style_cell(
		self,
		row_idx: int,
		col_idx: int,
		*,
		style_name: str | None = None,
		indent: int | None = None,
	):
		cell_key = (row_idx, col_idx)

		cell_style = self.config["cell_styles"].setdefault(cell_key, {})

		# Apply named style
		if style_name:
			cell_style.update(self.styles[style_name])

		# Apply indent style (overrides alignment from named style)
		if indent is not None:
			cell_style["alignment"] = self.styles[self.indent_key(indent)]["alignment"]

	def style_header(self, header_index: int):
		self.style_row(header_index, "header")

	def style_total_row(self, total_row_index: int):
		self.style_row(total_row_index, "total_row")

	def style_filter_labels(self, header_index: int):
		for row_idx in range(header_index - 1):
			self.style_cell(row_idx, 0, style_name="filter_label")

	def set_indentations(self, column: int, row_map: dict):
		for idx, row in row_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(idx, column, indent=row["indent"])

	def set_fieldtype_formats(self, columns: list[dict]):
		for idx, col in enumerate(columns):
			if style_name := self.FIELDTYPE_STYLES.get(col.get("fieldtype")):
				self.style_column(idx, style_name)

	def build(self) -> frappe._dict:
		return self.config

	@staticmethod
	@lru_cache(maxsize=1)
	def get_date_format() -> str:
		date_format = frappe.get_system_settings("date_format")
		return date_format.replace("mm", "MM")

	@staticmethod
	@lru_cache(maxsize=1)
	def get_time_format() -> str:
		return frappe.get_system_settings("time_format")

	@staticmethod
	def get_datetime_format() -> str:
		return f"{XLSXStyleBuilder.get_date_format()} {XLSXStyleBuilder.get_time_format()}"

	@staticmethod
	@lru_cache(maxsize=64)
	def get_number_format(
		fieldtype: Literal["Currency", "Int", "Float", "Percent"],
		currency: str | None = None,
	) -> str:
		from frappe.locale import get_number_format

		number_format = get_number_format()
		thousands_sep = number_format.thousands_separator
		decimal_sep = number_format.decimal_separator
		precision = number_format.precision

		if fieldtype == "Int":
			return "#,##0" if thousands_sep else "#0"

		elif fieldtype == "Currency":
			precision = cint(frappe.db.get_default("currency_precision")) or precision
			format_str = XLSXStyleBuilder._build_number_format(thousands_sep, decimal_sep, precision)
			currency_symbol, symbol_on_right = XLSXStyleBuilder._get_currency_symbol_info(currency)
			return XLSXStyleBuilder._get_currency_format(format_str, currency_symbol, symbol_on_right)

		elif fieldtype in ("Float", "Percent"):
			precision = cint(frappe.db.get_default("float_precision")) or precision
			format_str = XLSXStyleBuilder._build_number_format(thousands_sep, decimal_sep, precision)
			return f'{format_str}"%" ' if fieldtype == "Percent" else format_str

		return "General"

	@staticmethod
	@lru_cache(maxsize=64)
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

	@staticmethod
	def get_indent_style(indent_level: int, pt: int = 2) -> dict:
		return {"alignment": {"indent": indent_level * pt, "horizontal": "left"}}

	@staticmethod
	def _build_number_format(thousands_sep: str, decimal_sep: str, precision: int = 0) -> str:
		integer_part = "#,##0" if thousands_sep else "#0"
		decimal_part = (decimal_sep + "0" * precision) if precision > 0 else ""

		return f"{integer_part}{decimal_part}"

	@staticmethod
	def _get_currency_symbol_info(currency: str | None) -> tuple[str, bool]:
		if not currency or frappe.db.get_default("hide_currency_symbol") == "Yes":
			return "", False

		symbol, on_right = frappe.db.get_value("Currency", currency, ["symbol", "symbol_on_right"])

		return frappe._(symbol or currency), bool(on_right)

	@staticmethod
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

	@staticmethod
	def indent_key(level: int) -> str:
		return f"indent_{level}"


### Excel Creation Utils ###
def make_xlsx(
	data: list[list[Any]],
	sheet_name: str,
	wb: openpyxl.Workbook | None = None,
	column_widths: list[int] | None = None,
	styles: dict | None = None,
) -> BytesIO:
	"""
	Create an Excel file with the given data and formatting options.

	Args:
		data: List of rows, where each row is a list of cell values
		sheet_name: Name of the Excel sheet
		wb: Existing workbook to add sheet to. If None, creates new workbook
		column_widths: List of column widths in Excel units. If None, auto-sized
		styles: Configuration for cell/row/column styles
			- Should contain: column_styles, row_styles, cell_styles

	Returns:
			BytesIO: object containing the Excel file data
	"""

	def styling(obj, style: dict | None):
		if not style:
			return

		for prop, value in style.items():
			setattr(obj, prop, value)

	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}
	column_widths = column_widths or []
	styles = styles or {}

	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	ws = wb.create_sheet(INVALID_TITLE_REGEX.sub(" ", sheet_name), 0)

	for idx, width in enumerate(column_widths, start=1):
		if width:
			ws.column_dimensions[get_column_letter(idx)].width = width

	# Get style configurations
	column_styles = styles.get("column_styles") or {}
	row_styles = styles.get("row_styles") or {}
	cell_styles = styles.get("cell_styles") or {}

	styling_enabled = bool(column_styles or row_styles or cell_styles)

	for row_idx, row in enumerate(data):
		excel_row = []

		if styling_enabled:
			row_style = row_styles.get(row_idx) or {}

		for col_idx, value in enumerate(row):
			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			if styling_enabled:
				cell_style = cell_styles.get((row_idx, col_idx)) or {}
				col_style = column_styles.get(col_idx) or {}

				if not (cell_style or col_style or row_style):
					excel_row.append(cell)
					continue

				merged_style = {}

				# Merge styles: column_style < row_style < cell_style
				if col_style:
					merged_style.update(col_style)
				if row_style:
					merged_style.update(row_style)
				if cell_style:
					merged_style.update(cell_style)

				# Apply styles to cell
				if font := merged_style.get("font"):
					cell.font = font
				if fill := merged_style.get("fill"):
					cell.fill = fill
				if alignment := merged_style.get("alignment"):
					cell.alignment = alignment
				if border := merged_style.get("border"):
					cell.border = border
				if number_format := merged_style.get("number_format"):
					cell.number_format = number_format

			excel_row.append(cell)

		ws.append(excel_row)

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
