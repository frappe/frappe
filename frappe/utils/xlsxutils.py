# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from io import BytesIO
from typing import Any, Literal

import xlrd
import xlsxwriter
from openpyxl import load_workbook
from openpyxl.workbook.child import INVALID_TITLE_REGEX
from xlsxwriter.format import Format

import frappe
from frappe import _
from frappe.core.utils import html2text
from frappe.utils import cint
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)


### XLSX Formatter ###
@dataclass
class XLSXMetadata:
	"""
	Metadata for XLSX reports for exports.
	"""

	report_name: str = ""

	filters: dict = dataclass_field(default_factory=dict)

	row_map: dict[int, dict | list] = dataclass_field(default_factory=dict)
	column_map: dict[int, dict] = dataclass_field(default_factory=dict)

	header_index: int = 0
	last_row_index: int = 0
	max_indent_level: int = 0

	add_total_row: bool = False
	include_filters: bool = False
	ignore_visible_idx: bool = True
	include_indentation: bool = False
	include_hidden_columns: bool = False

	def get_column_index(self, fieldname: str) -> int | None:
		return next((idx for idx, col in self.column_map.items() if col.get("fieldname") == fieldname), None)

	def get_column(self, fieldname: str) -> dict | None:
		return next((col for col in self.column_map.values() if col.get("fieldname") == fieldname), None)

	def get_row(self, row_idx: int) -> dict | list | None:
		return self.row_map.get(row_idx)


class XLSXStyleBuilder:
	def __init__(self, metadata: XLSXMetadata):
		self.metadata = metadata

		self.styles = {}
		self.config = {
			"column_styles": {},
			"row_styles": {},
			"cell_styles": {},
		}

		self._set_defaults()

		self._register_default_highlight_styles()
		self._register_default_indent_styles()
		self._register_default_fieldtype_formats()

	### POST INIT METHODS ###
	def _set_defaults(self):
		self.currency_field_exists = any(
			col.get("fieldtype") == "Currency" for col in self.metadata.column_map.values()
		)

		self.currency_fields = {}

		if self.currency_field_exists:
			for idx, col in self.metadata.column_map.items():
				if col.get("fieldtype") == "Currency":
					self.currency_fields[idx] = col

	### STYLE REGISTRATION ###
	def _register_default_highlight_styles(self):
		highlight_styles = {
			"header": {"bold": True, "font_size": 12},
			"total_row": {"bold": True},
			"filter_label": {"bold": True},
		}

		for name, style in highlight_styles.items():
			self.register_style(name, style)

	def _register_default_indent_styles(self):
		if not self.metadata.max_indent_level:
			return

		for indent in range(self.metadata.max_indent_level + 1):
			self.register_style(self.indent_style_name(indent), {"align": "left", "indent": indent * 2})

	def _register_default_fieldtype_formats(self):
		map = {
			"float_format": self.get_number_format("Float"),
			"percent_format": self.get_number_format("Percent"),
			"date_format": self.get_date_format(),
			"time_format": self.get_time_format(),
			"datetime_format": self.get_datetime_format(),
		}

		for style_name, format in map.items():
			self.register_style(style_name, {"num_format": format})

	def register_currency_format(self, currency: str):
		if not currency:
			return self

		style_name = self.get_currency_style_name(currency)

		# format registered already
		if self.styles.get(style_name):
			return self

		number_format = self.get_number_format("Currency", currency)
		self.register_style(style_name, {"num_format": number_format})

		return self

	def register_style(self, name: str, style: dict):
		"""
		Register a named style for reuse across multiple cells/rows/columns.

		Args:
			name: Unique name for this style
			style: Dictionary of style properties
		"""
		self.styles[name] = style
		return self

	### STYLE APPLICATION ###
	def style_column(self, col_idx: int, style_name: str):
		self.config["column_styles"][col_idx] = style_name
		return self

	def style_row(self, row_idx: int, style_name: str):
		self.config["row_styles"][row_idx] = style_name
		return self

	def style_cell(self, row_idx: int, col_idx: int, style_name: str):
		self.config["cell_styles"][(row_idx, col_idx)] = style_name
		return self

	def build(self) -> frappe._dict:
		return {
			**self.config,
			"mapping": self.styles,
		}

	### Utility Methods ###
	def apply_default_styles(self, currency_formatting: bool = False, currency: str | dict | None = None):
		self.style_header()

		if self.metadata.include_filters:
			self.style_filters()

		if self.metadata.add_total_row and self.metadata.ignore_visible_idx:
			self.style_total_row()

		if self.metadata.include_indentation:
			self.apply_indentations(0)

		self.apply_default_fieldtype_formats(currency_formatting=currency_formatting, currency=currency)

		return self

	def style_header(self):
		return self.style_row(self.metadata.header_index, "header")

	def style_filters(self):
		LABEL_COLUMN_INDEX = 0

		for row_idx in range(self.metadata.header_index):
			self.style_cell(row_idx, LABEL_COLUMN_INDEX, "filter_label")

		return self

	def apply_indentations(self, column: int):
		for idx, row in self.metadata.row_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(idx, column, self.indent_style_name(row["indent"]))

		return self

	def style_total_row(self):
		return self.style_row(self.metadata.last_row_index, "total_row")

	def apply_default_fieldtype_formats(
		self, *, currency_formatting: bool = False, currency: str | dict | None = None
	):
		default_fieldtype_styles = {
			"Float": "float_format",
			"Percent": "percent_format",
			"Date": "date_format",
			"Time": "time_format",
			"Datetime": "datetime_format",
		}

		for idx, col in self.metadata.column_map.items():
			if style_name := default_fieldtype_styles.get(col.get("fieldtype")):
				self.style_column(idx, style_name)

		if currency_formatting:
			self.apply_currency_fieldtype_formats(currency)

		return self

	def apply_currency_fieldtype_formats(self, currency: str | dict | None = None):
		if not self.currency_field_exists:
			return self

		@frappe.request_cache
		def _register(currency: str) -> str:
			return self.register_currency_format(currency).get_currency_style_name(currency)

		# if single currency is provided, use it for all currency fields
		if isinstance(currency, str):
			style_name = _register(currency)

			for idx in self.currency_fields.keys():
				self.style_column(idx, style_name)

		# if currency mapping is provided, use it for respective fields
		elif isinstance(currency, dict):
			for fieldname, code in currency.items():
				if idx := self.metadata.get_column_index(fieldname):
					self.style_column(idx, _register(code))

		# currency per row based on metadata
		else:
			default_currency = frappe.db.get_default("currency")

			for row_idx, row in self.metadata.row_map.items():
				if not isinstance(row, dict):
					continue

				for col_idx, col in self.currency_fields.items():
					currency = self.get_field_currency(col, row) or default_currency

					self.style_cell(row_idx, col_idx, _register(currency))

		return self

	@staticmethod
	def get_field_currency(df: dict, doc: dict) -> str | None:
		fieldname = df.get("fieldname")
		options = df.get("options")

		if not (options and fieldname and doc):
			return

		if ":" in options:
			parts = options.split(":")
			if len(parts) == 3 and (docname := doc.get(parts[1])):
				return XLSXStyleBuilder._get_currency(parts[0], docname, parts[2])
			else:
				return
		else:
			return doc.get(options)

	@staticmethod
	@frappe.request_cache
	def _get_currency(doctype: str, docname: str, fieldname: str) -> str | None:
		return frappe.get_value(doctype, docname, fieldname)

	### Format Getters ###
	@staticmethod
	def get_date_format() -> str:
		return frappe.get_system_settings("date_format")

	@staticmethod
	def get_time_format() -> str:
		return frappe.get_system_settings("time_format")

	@staticmethod
	def get_datetime_format() -> str:
		return f"{XLSXStyleBuilder.get_date_format()} {XLSXStyleBuilder.get_time_format()}"

	@staticmethod
	@frappe.request_cache
	def get_number_format(
		fieldtype: Literal["Currency", "Float", "Percent"],
		currency: str | None = None,
	) -> str:
		from frappe.locale import get_number_format as _get_format

		number_format = _get_format()
		thousands_sep = number_format.thousands_separator
		decimal_sep = number_format.decimal_separator
		precision = number_format.precision

		if fieldtype == "Currency":
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
	def get_currency_style_name(currency: str) -> str:
		return f"{currency.lower()}_currency_format"

	@staticmethod
	def indent_style_name(indent: int) -> str:
		return f"indent_{indent}"


### Excel Creation ###
def make_xlsx(
	data: list[list[Any]],
	sheet_name: str,
	wb: xlsxwriter.Workbook | None = None,
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
		styles: Dictionary defining styles for cells, rows, and columns
			- mapping: dict of style name to style properties
			- column_styles: dict of column index to style name
			- row_styles: dict of row index to style name
			- cell_styles: dict of (row index, column index) to style name

	Returns:
		BytesIO: object containing the Excel file data
	"""
	column_widths = column_widths or []
	styles = styles or {}

	# creating workbook
	xlsx_file = BytesIO()
	created_wb = wb is None  # to know to close it later

	if created_wb:
		wb = xlsxwriter.Workbook(xlsx_file, {"in_memory": True})

	# sanitize sheet name
	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.add_worksheet(sheet_name_sanitized[:31])

	# set column widths
	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.set_column(i, i, column_width)

	# handle styles
	style_map: dict = styles.get("mapping") or {}
	col_styles: dict[int, str] = styles.get("column_styles") or {}
	row_styles: dict[int, str] = styles.get("row_styles") or {}
	cell_styles: dict[tuple[int, int], str] = styles.get("cell_styles") or {}
	format_map: dict[tuple[str, ...], Format] = {}

	styling_enabled = bool(col_styles or row_styles or cell_styles)

	if not styling_enabled:
		ws.set_row(0, cell_format=wb.add_format({"bold": True}))

	def get_style_names(r: int, c: int) -> Iterator[str]:
		yield col_styles.get(c)
		yield row_styles.get(r)
		yield cell_styles.get((r, c))

	def get_cell_style(r: int, c: int):
		key = tuple(s for s in get_style_names(r, c) if s is not None)
		if not key:
			return

		format = format_map.get(key)
		if not format:
			if len(key) == 1:
				style_dict = style_map.get(key[0]) or {}
			else:
				style_dict = {}
				for style_name in key:
					# priority: cell > row > column
					style_dict.update(style_map.get(style_name) or {})

			format = wb.add_format(style_dict)
			format_map[key] = format

		return format

	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}

	for row_idx, row in enumerate(data):
		for col_idx, value in enumerate(row):
			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell_format = get_cell_style(row_idx, col_idx) if styling_enabled else None
			ws.write(row_idx, col_idx, value, cell_format)

	if created_wb:
		wb.close()

	xlsx_file.seek(0)
	return xlsx_file


### Utilities ###
def handle_html(data: str) -> str:
	# return if no html tags found
	if "<" not in data or ">" not in data:
		return data

	h = unescape_html(data or "")

	try:
		value = html2text(h, strip_links=True, wrap=False)
	except Exception:
		# unable to parse html, send it raw
		return data

	return value.replace("  \n", ", ").replace("\n", " ").replace("# ", ", ")


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
