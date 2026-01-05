# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass, field
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
# TODO: Date and Time formats not working properly need to fix


class XLSXStyleBuilder:
	"""Utility class for building Excel styles and formatting."""

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
			"conditional_styles": [],
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
		style_name = style_name or f"{currency}_currency_format"
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

	def add_conditional_style(self, condition: Callable[[int, int, Any], bool], style_name: str):
		self.config["conditional_styles"].append({"condition": condition, "style": self.styles[style_name]})

	def style_header(self, header_index: int):
		self.style_row(header_index, "header")

	def style_filter_labels(self, header_index: int):
		for row_idx in range(header_index):
			self.style_cell(row_idx, 0, style_name="filter_label")

	def set_indentations(self, column: int, row_map: dict):
		for idx, row in row_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(idx, column, indent=row["indent"])

	def set_fieldtype_number_format(self, columns: list[dict]):
		for idx, col in enumerate(columns):
			if style_name := self.FIELDTYPE_STYLES.get(col.get("fieldtype")):
				self.style_column(idx, style_name)

	def build(self) -> frappe._dict:
		return self.config

	@staticmethod
	@lru_cache(maxsize=1)
	def get_date_format() -> str:
		date_format = frappe.get_system_settings("date_format")
		return date_format.replace("mm", "MM").upper()

	@staticmethod
	@lru_cache(maxsize=1)
	def get_time_format() -> str:
		return frappe.get_system_settings("time_format").upper()

	@staticmethod
	@lru_cache(maxsize=1)
	def get_datetime_format() -> str:
		return f"{XLSXStyleBuilder.get_date_format()} {XLSXStyleBuilder.get_time_format()}"

	@staticmethod
	@lru_cache(maxsize=128)
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

	@staticmethod
	@lru_cache(maxsize=64)
	def get_indent_style(indent_level: int, pt: int = 2) -> dict:
		return {"alignment": {"indent": indent_level * pt, "horizontal": "left"}}

	@staticmethod
	def _build_number_format(thousands_sep: str, decimal_sep: str, precision: int = 0) -> str:
		"""Helper to build number format string."""
		integer_part = "#,##0" if thousands_sep else "#0"
		decimal_part = (decimal_sep + "0" * precision) if precision > 0 else ""
		return f"{integer_part}{decimal_part}"

	@staticmethod
	def _get_currency_symbol_info(currency: str | None) -> tuple[str, bool]:
		"""Helper to get currency symbol and position."""
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
		"""Helper to apply currency symbol to format."""
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
	styles = styles or {}

	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.create_sheet(sheet_name_sanitized, 0)

	# TODO: it is also updating filters column width need to fix
	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.column_dimensions[get_column_letter(i + 1)].width = column_width

	# Get style configurations
	column_styles = styles.get("column_styles", {})
	row_styles = styles.get("row_styles", {})
	cell_styles = styles.get("cell_styles", {})
	conditional_styles = styles.get("conditional_styles", [])

	for row_idx, row in enumerate(data):
		clean_row = []

		for col_idx, item in enumerate(row):
			if isinstance(item, str) and (sheet_name not in ["Data Import Template", "Data Export"]):
				value = handle_html(item)
			else:
				value = item

			if isinstance(value, str) and next(ILLEGAL_CHARACTERS_RE.finditer(value), None):
				# Remove illegal characters from the string
				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			styles_to_merge = []

			# 1. Column-wide style (lowest priority)
			if col_style := column_styles.get(col_idx):
				styles_to_merge.append(col_style)

			# 2. Row-wide style
			if row_style := row_styles.get(row_idx):
				styles_to_merge.append(row_style)

			# 3. Conditional styles
			for cond_style in conditional_styles:
				try:
					if cond_style["condition"](row_idx, col_idx, value):
						styles_to_merge.append(cond_style["style"])
				except Exception:
					# skip if condition function fails
					pass

			# 4. Specific cell style (highest priority)
			if cell_style := cell_styles.get((row_idx, col_idx)):
				styles_to_merge.append(cell_style)

			style = {}

			for s in styles_to_merge:
				style.update(s)

			# Apply the merged style to the cell
			if style:
				for prop in ("font", "fill", "number_format", "alignment", "border"):
					if value := style.get(prop):
						setattr(cell, prop, value)

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
