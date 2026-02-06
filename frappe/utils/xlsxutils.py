# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import functools
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from io import BytesIO
from typing import Any, ClassVar, Literal

import openpyxl
import xlrd
import xlsxwriter
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from xlsxwriter.format import Format

import frappe
from frappe import _
from frappe.core.utils import html2text
from frappe.utils import cint
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)

INVALID_SHEET_NAME_RE = re.compile(r"[\[\]:*?/\\]")
MAX_SHEET_NAME_LENGTH = 31


### XLSX Formatter ###
@dataclass(slots=True)
class XLSXMetadata:
	"""
	Metadata for XLSX reports for exports.

	NOTE:
	- indexes based on excel sheet rows/columns position (0-indexed)
	"""

	report_name: str = ""

	filters: dict = dataclass_field(default_factory=dict)

	column_map: dict[int, dict] = dataclass_field(default_factory=dict)
	row_map: dict[int, dict | list] = dataclass_field(default_factory=dict)
	applied_filters_map: dict[int, list] = dataclass_field(default_factory=dict)

	add_total_row: bool = False
	include_filters: bool = False
	ignore_visible_idx: bool = True
	include_indentation: bool = False

	def get_column_index(self, fieldname: str) -> int | None:
		return next((idx for idx, col in self.column_map.items() if col.get("fieldname") == fieldname), None)

	def get_column(self, fieldname: str) -> dict | None:
		return next((col for col in self.column_map.values() if col.get("fieldname") == fieldname), None)

	def get_row(self, row_idx: int) -> dict | list | None:
		return self.row_map.get(row_idx)

	def get_header_index(self) -> int:
		return get_report_header_index(list(self.applied_filters_map.values()))

	def get_first_row_index(self) -> int:
		return min(self.row_map.keys()) if self.row_map else 0

	def get_last_row_index(self) -> int:
		return max(self.row_map.keys()) if self.row_map else 0


class XLSXStyleBuilder:
	RIGHT_ALIGN_FIELDS: ClassVar[set[str]] = {
		*frappe.model.numeric_fieldtypes,
		*frappe.model.datetime_fields,
		"Rating",
	}

	def __init__(self, metadata: XLSXMetadata, default_styling: bool = True):
		self.metadata = metadata

		# column fieldname -> index mapping
		self.field_index = {
			col.get("fieldname"): idx for idx, col in self.metadata.column_map.items() if col.get("fieldname")
		}

		self.styles: list[dict] = []
		self.column_styles: dict[int, list[int]] = {}
		self.row_styles: dict[int, list[int]] = {}
		self.cell_styles: dict[tuple[int, int], list[int]] = {}

		self.result = {
			"styles": self.styles,
			"column_styles": self.column_styles,
			"row_styles": self.row_styles,
			"cell_styles": self.cell_styles,
		}

		# caches
		self.currency_styles = {}
		self.indent_styles = {}

		if default_styling:
			self.apply_default_styles()

	### STYLE REGISTRATION ###
	def register_style(self, style: dict) -> int:
		if not style:
			frappe.throw(_("Cannot register an empty style."))

		style_id = len(self.styles)
		self.styles.append(style)

		return style_id

	def register_currency_style(self, currency: str) -> int | None:
		if currency not in self.currency_styles:
			self.currency_styles[currency] = self.register_style(
				{"num_format": self.get_number_format("Currency", currency)}
			)

		return self.currency_styles[currency]

	def register_indent_style(self, indent: int) -> int | None:
		if indent not in self.indent_styles:
			self.indent_styles[indent] = self.register_style({"align": "left", "indent": indent * 2})

		return self.indent_styles[indent]

	### STYLE APPLICATION ###
	def style_column(self, col_idx: int, style_id: int):
		if style_id is None:
			return self

		if col_idx not in self.column_styles:
			self.column_styles[col_idx] = []

		self.column_styles[col_idx].append(style_id)

		return self

	def style_row(self, row_idx: int, style_id: int):
		if style_id is None:
			return self

		if row_idx not in self.row_styles:
			self.row_styles[row_idx] = []

		self.row_styles[row_idx].append(style_id)

		return self

	def style_cell(self, row_idx: int, col_idx: int, style_id: int):
		if style_id is None:
			return self

		key = (row_idx, col_idx)

		if key not in self.cell_styles:
			self.cell_styles[key] = []

		self.cell_styles[key].append(style_id)

		return self

	### UTILITY METHODS FOR STYLING ###
	def apply_default_styles(self, currency_formatting: bool = True):
		self.style_header()

		if self.metadata.include_filters:
			self.style_filters()

		if self.metadata.add_total_row and self.metadata.ignore_visible_idx:
			self.style_total_row()

		if self.metadata.include_indentation:
			self.apply_indentations(0)

		self.apply_default_fieldtype_formats(currency_formatting)

		return self

	def style_header(self):
		header_index = self.metadata.get_header_index()

		self.style_row(header_index, self.register_style({"bold": True, "font_size": 13}))

		right_align = self.register_style({"align": "right"})
		left_align = self.register_style({"align": "left"})

		for col_idx, col in self.metadata.column_map.items():
			self.style_cell(
				header_index,
				col_idx,
				right_align if self.is_right_align(col.get("fieldtype")) else left_align,
			)

		return self

	def style_filters(self):
		style = self.register_style({"bold": True})

		for row_idx in self.metadata.applied_filters_map.keys():
			# style only the label column (0th index)
			self.style_cell(row_idx, 0, style)
		return self

	def apply_indentations(self, col_idx: int, field: str = "indent"):
		for row_idx, row in self.metadata.row_map.items():
			if isinstance(row, dict) and (indent := row.get(field)):
				self.style_cell(row_idx, col_idx, self.register_indent_style(indent))

		return self

	def style_total_row(self):
		return self.style_row(
			self.metadata.get_last_row_index(), self.register_style({"bold": True, "font_size": 12})
		)

	def apply_default_fieldtype_formats(self, currency_formatting: bool = True):
		formats: dict[str, int] = {
			"Float": self.register_style({"num_format": self.get_number_format("Float")}),
			"Percent": self.register_style({"num_format": self.get_number_format("Percent")}),
			"Date": self.register_style({"num_format": self.get_date_format()}),
			"Time": self.register_style({"num_format": self.get_time_format()}),
			"Datetime": self.register_style({"num_format": self.get_datetime_format()}),
		}

		for idx, col in self.metadata.column_map.items():
			style_id = formats.get(col.get("fieldtype"))

			if style_id is not None:
				self.style_column(idx, style_id)

		if currency_formatting:
			self.apply_currency_fieldtype_formats()

		return self

	def apply_currency_fieldtype_formats(self):
		currency_fields = self.get_fields_mapping("Currency")

		if not currency_fields:
			return self

		default_currency = frappe.db.get_default("currency")

		field_index = self.field_index
		last_row_index = self.metadata.get_last_row_index()
		skip_last_row = self.metadata.add_total_row and self.metadata.ignore_visible_idx
		row_is_dict = isinstance(self.metadata.get_row(self.metadata.get_first_row_index()), dict)

		# helpers
		@functools.cache
		def _get_value(doctype: str, docname: str, fieldname: str) -> str | None:
			return frappe.get_value(doctype, docname, fieldname)

		@functools.cache
		def parse_options(options: str) -> tuple:
			if ":" in options:
				parts = options.split(":")
				if len(parts) == 3:
					doctype, link_field, curr_field = parts
					link_idx = None if row_is_dict else field_index.get(link_field)
					curr_field_idx = None if row_is_dict else field_index.get(curr_field)
					return (doctype, link_field, link_idx, curr_field, curr_field_idx)

			return (None, None, None, options, None if row_is_dict else field_index.get(options))

		def get_currency(options: str, row: list | dict) -> str | None:
			if not options or not row:
				return None

			doctype, link_field, link_idx, curr_field, curr_field_idx = parse_options(options)

			# linked document lookup
			if doctype:
				link_value = (
					row.get(link_field) if row_is_dict else (row[link_idx] if link_idx is not None else None)
				)

				if not link_value:
					return None

				return _get_value(doctype, link_value, curr_field)

			# direct field reference
			if row_is_dict:
				return row.get(curr_field)

			return row[curr_field_idx] if curr_field_idx is not None else None

		# apply formatting
		for row_idx, row in self.metadata.row_map.items():
			if row_idx == last_row_index and skip_last_row:
				continue

			for col_idx, col in currency_fields.items():
				currency = get_currency(col.get("options"), row) or default_currency
				self.style_cell(row_idx, col_idx, self.register_currency_style(currency))

		return self

	### CURRENCY RESOLUTION ###
	def get_fields_mapping(self, fieldtype: str | None = None) -> dict[int, dict]:
		return {
			col_idx: col
			for col_idx, col in self.metadata.column_map.items()
			if not fieldtype or col.get("fieldtype") == fieldtype
		}

	@staticmethod
	def _get_currency_symbol_info(currency: str | None) -> tuple[str, bool]:
		if not currency or frappe.db.get_default("hide_currency_symbol") == "Yes":
			return "", False

		symbol, on_right = frappe.db.get_value("Currency", currency, ["symbol", "symbol_on_right"])

		return frappe._(symbol or currency), bool(on_right)

	@staticmethod
	def _build_currency_format(
		format_string: str,
		currency_symbol: str | None = None,
		symbol_on_right: bool = False,
	) -> str:
		if not currency_symbol:
			return format_string

		if symbol_on_right:
			return f'{format_string}" {currency_symbol}";-{format_string}" {currency_symbol}"'

		return f'"{currency_symbol} "{format_string};"{currency_symbol} "-{format_string}'

	### FORMAT GETTERS ###
	@staticmethod
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
			return XLSXStyleBuilder._build_currency_format(format_str, currency_symbol, symbol_on_right)

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
	def get_date_format() -> str:
		return frappe.get_system_settings("date_format")

	@staticmethod
	def get_time_format() -> str:
		return frappe.get_system_settings("time_format")

	@staticmethod
	def get_datetime_format() -> str:
		return f"{XLSXStyleBuilder.get_date_format()} {XLSXStyleBuilder.get_time_format()}"

	@staticmethod
	def is_right_align(fieldtype: str) -> bool:
		return fieldtype in XLSXStyleBuilder.RIGHT_ALIGN_FIELDS


def get_default_xlsx_styles(
	columns: list[dict],
	data: list[list | dict],
	applied_filters: list[list] | None = None,
	*,
	report_name: str = "",
	filters: dict | None = None,
	has_total_row: bool = False,
	has_filters: bool = False,
	has_indentation: bool = False,
	currency_formatting: bool = True,
) -> dict:
	"""
	Generate default XLSX styles for xlsx exports.

	Args:
		columns: Column definitions with keys: fieldname, fieldtype, label, options.
		data: Row data as list of dicts or lists (excluding header and filter rows).
		applied_filters: Filter rows to display at top of sheet. Each item is [label, value].
		report_name: Name of the report.
		filters: Raw filters dict (fieldname -> value).
		has_total_row: If True, applies bold styling to the last row.
		ignore_total_row: If True, skips styling the total row.
		has_filters: If True, applies bold styling to filter labels.
		has_indentation: If True, applies indent styles based on row's 'indent' key.
		apply_currency_format: If True, applies currency number formats to Currency fields.
		currency: Currency for formatting. Can be:
			- str: Single currency code for all Currency fields (e.g., "USD")
			- dict: Mapping of fieldname -> currency code for per-field formatting
			- None: Resolves currency per-row from field options
	"""
	applied_filters = applied_filters or []
	filters = filters or {}

	header_index = get_report_header_index(applied_filters)

	applied_filters_map = dict(enumerate(applied_filters))
	column_map = dict(enumerate(columns))
	row_map = dict(enumerate(data, start=header_index + 1))  # +1 for header row

	metadata = XLSXMetadata(
		report_name=report_name,
		filters=filters,
		column_map=column_map,
		row_map=row_map,
		applied_filters_map=applied_filters_map,
		add_total_row=has_total_row,
		include_filters=has_filters,
		include_indentation=has_indentation,
	)

	return XLSXStyleBuilder(metadata, default_styling=False).apply_default_styles(currency_formatting).result


def get_report_header_index(applied_filters: list[list]) -> int:
	return len(applied_filters) + 1 if applied_filters else 0  # +1 for empty row after filters


### Excel Creation ###
def make_xlsx(
	data: list[list[Any]],
	sheet_name: str,
	wb: xlsxwriter.Workbook | None = None,
	column_widths: list[int] | None = None,
	styles: dict | None = None,
) -> BytesIO | None:
	"""
	Create an Excel file with the given data and formatting options.

	Args:
		data: List of rows, where each row is a list of cell values
		sheet_name: Name of the Excel sheet
		wb: Existing workbook to add sheet to. If None, creates new workbook
			- Workbook must be closed by caller if provided
			- Should be created with constant_memory=True for large datasets
		column_widths: List of column widths in Excel units. If None, auto-sized
		styles: Dictionary defining styles for cells, rows, and columns
			- styles: list of style dicts
			- column_styles: dict of column index to list of style ids
			- row_styles: dict of row index to list of style ids
			- cell_styles: dict of (row index, column index) to list of style ids
	Returns:
		BytesIO | None: BytesIO object containing the Excel file data if a new workbook was created, otherwise None

	"""
	column_widths = column_widths or []
	styles = styles or {}

	# creating workbook
	xlsx_file = None
	created_wb = wb is None  # to know to close it later

	if created_wb:
		xlsx_file = BytesIO()
		options = {"constant_memory": True}

		if not styles:
			options["default_date_format"] = XLSXStyleBuilder.get_datetime_format()

		wb = xlsxwriter.Workbook(xlsx_file, options)

	ws = wb.add_worksheet(get_sanitized_sheet_name(sheet_name))

	# extract style components
	def _extract_ids(key: str) -> dict:
		return {k: tuple(v) for k, v in (styles.get(key) or {}).items() if v}

	style_registry: list[dict] = styles.get("styles") or []
	col_style_ids: dict[int, tuple[int, ...]] = _extract_ids("column_styles")
	row_style_ids: dict[int, tuple[int, ...]] = _extract_ids("row_styles")
	cell_style_ids: dict[tuple[int, int], tuple[int, ...]] = _extract_ids("cell_styles")

	styling_enabled = bool(col_style_ids or row_style_ids or cell_style_ids)

	if not styling_enabled:
		ws.set_row(0, cell_format=wb.add_format({"bold": True}))

	def resolve_style_ids(style_ids: tuple[int, ...]) -> dict:
		if len(style_ids) == 1:
			return style_registry[style_ids[0]]

		result = {}

		for sid in style_ids:
			result.update(style_registry[sid])
		return result

	@functools.cache
	def get_format(style_ids: tuple[int, ...]) -> Format:
		return wb.add_format(resolve_style_ids(style_ids))

	# set column widths
	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.set_column(i, i, column_width)

	# column level styles
	for col_idx, style_ids in col_style_ids.items():
		ws.set_column(col_idx, col_idx, cell_format=get_format(style_ids))

	# row level styles
	for row_idx, style_ids in sorted(row_style_ids.items()):
		ws.set_row(row_idx, cell_format=get_format(style_ids))

	# priority: column < row < cell (later in tuple = higher priority)
	cell_formats: dict[tuple[int, int], Format] = {}

	# process explicit cell styles
	for pos, cell_ids in cell_style_ids.items():
		row_idx, col_idx = pos
		col_ids = col_style_ids.get(col_idx, ())
		row_ids = row_style_ids.get(row_idx, ())

		cell_formats[pos] = get_format(col_ids + row_ids + cell_ids)

	# process row x column intersections (no explicit cell style)
	for row_idx, row_ids in row_style_ids.items():
		for col_idx, col_ids in col_style_ids.items():
			pos = (row_idx, col_idx)
			if pos not in cell_formats:
				cell_formats[pos] = get_format(col_ids + row_ids)

	handle_html_content = should_handle_html_content(sheet_name)

	# pre-compile check for illegal characters
	illegal_chars_search = ILLEGAL_CHARACTERS_RE.search
	illegal_chars_sub = ILLEGAL_CHARACTERS_RE.sub

	# bind method for hot loop
	write = ws.write
	has_cell_formats = bool(cell_formats)
	get_cell_format = cell_formats.get

	for row_idx, row in enumerate(data):
		for col_idx, value in enumerate(row):
			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				if illegal_chars_search(value):
					value = illegal_chars_sub("", value)

			cell_format = get_cell_format((row_idx, col_idx)) if has_cell_formats else None

			write(row_idx, col_idx, value, cell_format)

	if created_wb:
		wb.close()
		xlsx_file.seek(0)

	return xlsx_file


def make_xls(
	data: list[list[Any]],
	sheet_name: str,
	wb: openpyxl.Workbook | None = None,
	column_widths: list[int] | None = None,
) -> BytesIO:
	"""
	Create an Excel file (old format xls) with the given data and formatting options.

	Args:
		data: List of rows, where each row is a list of cell values
		sheet_name: Name of the Excel sheet
		wb: Existing workbook to add sheet to. If None, creates new workbook
		column_widths: List of column widths in Excel units. If None, auto-sized

	Returns:
		BytesIO: BytesIO object containing the Excel file data
	"""
	column_widths = column_widths or []

	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	ws = wb.create_sheet(get_sanitized_sheet_name(sheet_name), 0)

	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.column_dimensions[get_column_letter(i + 1)].width = column_width

	ws.row_dimensions[1].font = Font(name="Calibri", bold=True)

	date_format = XLSXStyleBuilder.get_date_format()
	time_format = XLSXStyleBuilder.get_time_format()
	datetime_format = XLSXStyleBuilder.get_datetime_format()

	handle_html_content = should_handle_html_content(sheet_name)

	# pre-compile check for illegal characters
	illegal_chars_search = ILLEGAL_CHARACTERS_RE.search
	illegal_chars_sub = ILLEGAL_CHARACTERS_RE.sub

	for row in data:
		excel_row = []

		for value in row:
			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				if illegal_chars_search(value):
					value = illegal_chars_sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			# date/time formatting
			if isinstance(value, datetime.datetime):
				cell.number_format = datetime_format
			elif isinstance(value, datetime.date):
				cell.number_format = date_format
			elif isinstance(value, datetime.time):
				cell.number_format = time_format

			excel_row.append(cell)

		ws.append(excel_row)

	file = BytesIO()

	wb.save(file)
	return file


def get_sanitized_sheet_name(name: str) -> str:
	return INVALID_SHEET_NAME_RE.sub(" ", name)[:MAX_SHEET_NAME_LENGTH]


def should_handle_html_content(sheet_name: str) -> bool:
	return sheet_name not in {"Data Import Template", "Data Export"}


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


def build_xlsx_response(data, filename, styles: dict | None = None):
	from frappe.desk.utils import provide_binary_file

	provide_binary_file(filename, "xlsx", make_xlsx(data, filename, styles=styles).getvalue())
