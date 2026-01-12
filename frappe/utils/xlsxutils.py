# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
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


### XLSX Formatter ###
@dataclass
class XLSXMetadata:
	report_name: str = ""

	filters: dict = dataclass_field(default_factory=dict)
	columns: list[dict] = dataclass_field(default_factory=list)
	rows_map: dict[int, dict | list] = dataclass_field(default_factory=dict)

	header_index: int = 0
	last_row_index: int = 0
	max_indent_level: int = 0

	add_total_row: bool = False
	include_filters: bool = False
	ignore_visible_idx: bool = True
	include_indentation: bool = False
	include_hidden_columns: bool = False


class XLSXStyleBuilder:
	# Mapping of style property names to their openpyxl classes
	STYLE_CLASSES: ClassVar[dict] = {
		"font": Font,
		"fill": PatternFill,
		"alignment": Alignment,
	}

	# Border sides that need Side object conversion
	BORDER_SIDES: ClassVar[tuple] = ("left", "right", "top", "bottom", "diagonal")
	_border_cache: ClassVar[dict] = {}

	DEFAULT_MAX_INDENT: ClassVar[int] = 2

	def __init__(self, metadata: XLSXMetadata, default_styling: bool = False):
		self.metadata = metadata

		self.styles = {}

		self.default_fieldtype_styles = {
			"Float": "float_format",
			"Percent": "percent_format",
			"Date": "date_format",
			"Time": "time_format",
			"Datetime": "datetime_format",
		}

		self.standard_styles = {
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

		self.config = {
			"column_styles": {},
			"row_styles": {},
			"cell_styles": {},
		}

		self.column_map: dict[str, int] = {}
		self.build_column_maps()

		self._register_standard_styles()
		self._register_default_indent_styles()
		self._register_default_fieldtype_formats()
		self._set_defaults()

		if default_styling:
			self.apply_default_styles()

	### POST INIT METHODS ###
	def _set_defaults(self):
		self.currency_field_exists = any(col.get("fieldtype") == "Currency" for col in self.metadata.columns)
		self.currency_fields = {}

		if self.currency_field_exists:
			for idx, col in enumerate(self.metadata.columns):
				if col.get("fieldtype") == "Currency":
					self.currency_fields[idx] = col

	### META DATA METHODS ###
	def build_column_maps(self):
		self.column_map.clear()

		for idx, column in enumerate(self.metadata.columns):
			if fieldname := column.get("fieldname"):
				self.column_map[fieldname] = idx

	def get_column(self, fieldname: str) -> dict | None:
		if idx := self.column_map.get(fieldname):
			return self.metadata.columns[idx]

		return None

	def get_column_index(self, fieldname: str) -> int | None:
		return self.column_map.get(fieldname)

	def get_row(self, row_idx: int) -> dict | list | None:
		return self.metadata.rows_map.get(row_idx)

	### STYLE REGISTRATION ###
	def _register_standard_styles(self):
		for name, style in self.standard_styles.items():
			self.register_style(name, **style)

	def _register_default_indent_styles(self):
		max_indent = (
			self.metadata.max_indent_level
			if self.metadata.max_indent_level is not None
			else self.DEFAULT_MAX_INDENT
		)

		for indent in range(max_indent + 1):
			self.register_style(self.get_indent_style_name(indent), **self.get_indent_style(indent))

	def _register_default_fieldtype_formats(self):
		map = {
			"float_format": self.get_number_format("Float"),
			"percent_format": self.get_number_format("Percent"),
			"date_format": self.get_date_format(),
			"time_format": self.get_time_format(),
			"datetime_format": self.get_datetime_format(),
		}

		for style_name, format in map.items():
			self.register_style(style_name, number_format=format)

	def register_currency_format(self, currency: str):
		if not currency:
			return self

		style_name = self.get_currency_style_name(currency)

		# format registered already
		if self.get_style(style_name):
			return self

		number_format = self.get_number_format("Currency", currency)
		self.register_style(style_name, number_format=number_format)

		return self

	def register_new_fieldtype_format(
		self,
		fieldtype: str,
		format: str,
		name: str | None = None,
	):
		style_name = name or f"{fieldtype.lower().replace(' ', '_')}_format"

		if style_name:
			self.register_style(style_name, number_format=format)

			self.default_fieldtype_styles[fieldtype] = style_name

		return self

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
				For dict config, sides (left, right, top, bottom, diagonal) can be:
				- Side object directly
				- dict with Side kwargs: {"border_style": "thin", "color": "000000"}
		"""
		style = frappe._dict()

		# Handle number format
		if number_format := kwargs.get("number_format"):
			style.number_format = number_format

		# Handle style objects with automatic instantiation
		for prop_name, style_class in self.STYLE_CLASSES.items():
			if config := kwargs.get(prop_name):
				style[prop_name] = style_class(**config) if isinstance(config, dict) else config

		# Handle border separately (needs Side object conversion)
		if border_config := kwargs.get("border"):
			style.border = self._create_border(border_config)

		self.styles[name] = style

		return self

	### STYLE APPLICATION ###
	def get_style(self, style_name: str) -> dict | None:
		return self.styles.get(style_name)

	def style_column(self, col_idx: int, style_name: str):
		if style := self.get_style(style_name):
			self.config["column_styles"][col_idx] = style

		return self

	def style_row(self, row_idx: int, style_name: str):
		if style := self.get_style(style_name):
			self.config["row_styles"][row_idx] = style

		return self

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
		if style_name and (style := self.get_style(style_name)):
			cell_style.update(style)

		# Apply indent style (overrides alignment from named style)
		if indent is not None and (style := self.get_style(self.get_indent_style_name(indent))):
			cell_style["alignment"] = style["alignment"]

		return self

	def style_cell_range(
		self,
		start_row: int,
		end_row: int,
		start_col: int,
		end_col: int,
		style_name: str,
	):
		if style := self.get_style(style_name):
			cell_styles = self.config["cell_styles"]
			for row_idx in range(start_row, end_row + 1):
				for col_idx in range(start_col, end_col + 1):
					cell_styles.setdefault((row_idx, col_idx), {}).update(style)

		return self

	def style_column_range(
		self,
		col_idx: int,
		start_row: int,
		end_row: int,
		style_name: str,
	):
		return self.style_cell_range(start_row, end_row, col_idx, col_idx, style_name)

	def style_row_range(
		self,
		row_idx: int,
		start_col: int,
		end_col: int,
		style_name: str,
	):
		return self.style_cell_range(row_idx, row_idx, start_col, end_col, style_name)

	def build(self) -> frappe._dict:
		return self.config

	### Utility Methods ###
	def apply_default_styles(self):
		self.style_header()

		if self.metadata.include_filters:
			self.style_filters()

		if self.metadata.add_total_row and self.metadata.ignore_visible_idx:
			self.style_total_row()

		if self.metadata.include_indentation:
			self.apply_indentations(0)

		return self

	def style_header(self):
		return self.style_row(self.metadata.header_index, "header")

	def style_filters(self):
		return self.style_column_range(0, 0, self.metadata.header_index - 1, "filter_label")

	def apply_indentations(self, column: int):
		for idx, row in self.metadata.rows_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(idx, column, indent=row["indent"])
		return self

	def style_total_row(self):
		return self.style_row(self.metadata.last_row_index, "total_row")

	def apply_default_fieldtype_formats(
		self, *, currency_formatting: bool = False, currency: str | dict | None = None
	):
		for idx, col in enumerate(self.metadata.columns):
			if style_name := self.default_fieldtype_styles.get(col.get("fieldtype")):
				self.style_column(idx, style_name)

		if currency_formatting:
			self.apply_currency_fieldtype_formats(currency)

		return self

	def apply_currency_fieldtype_formats(self, currency: str | dict | None = None):
		if not self.currency_field_exists:
			return self

		@lru_cache(maxsize=64)
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
				if idx := self.get_column_index(fieldname):
					self.style_column(idx, _register(code))

		# currency per row based on metadata
		else:
			default_currency = frappe.db.get_default("currency")

			for row_idx, row in self.metadata.rows_map.items():
				if not isinstance(row, dict):
					continue

				for col_idx, col in self.currency_fields.items():
					currency = self.get_field_currency(col, row) or default_currency

					style_name = _register(currency)
					self.style_cell(row_idx, col_idx, style_name=style_name)

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
	@lru_cache(maxsize=64)
	def _get_currency(doctype: str, docname: str, fieldname: str) -> str | None:
		return frappe.get_value(doctype, docname, fieldname)

	@staticmethod
	def _create_border(config) -> Border:
		if isinstance(config, Border):
			return config

		key = XLSXStyleBuilder._border_config_to_key(config)

		if key in XLSXStyleBuilder._border_cache:
			return XLSXStyleBuilder._border_cache[key]

		border_kwargs = {k: (Side(**v) if isinstance(v, dict) else v) for k, v in config.items()}

		border = Border(**border_kwargs)
		XLSXStyleBuilder._border_cache[key] = border

		return border

	@staticmethod
	def _border_config_to_key(config: dict) -> tuple:
		get = config.get
		items = []

		# use deterministic ordering
		for key in XLSXStyleBuilder.BORDER_SIDES:
			value = get(key)
			if value is None:
				continue

			if isinstance(value, dict):
				items.append((key, tuple(value.items())))
			elif isinstance(value, Side):
				d = value.__dict__
				items.append((key, (d.get("style"), d.get("color"), d.get("border_style"))))
			else:
				items.append((key, value))

		return tuple(items)

	### Format Getters ###
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

	#### Excel Color Utils ####
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

	### Indent Style Utils ###
	@staticmethod
	def get_indent_style(indent_level: int, pt: int = 2) -> dict:
		return {"alignment": {"indent": indent_level * pt, "horizontal": "left"}}

	@staticmethod
	def get_indent_style_name(level: int) -> str:
		return f"indent_{level}"


### Excel Creation ###
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
	column_widths = column_widths or []
	styles = styles or {}

	# Create workbook and worksheet
	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	ws = wb.create_sheet(INVALID_TITLE_REGEX.sub(" ", sheet_name), 0)

	# Set column widths
	_set_column_widths(ws, column_widths)

	# Write data rows
	_write_data_rows(ws=ws, data=data, sheet_name=sheet_name, styles=styles)

	# Save and return
	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	return xlsx_file


def _set_column_widths(ws, column_widths: list[int] | None = None) -> None:
	"""
	Set column widths on the worksheet.
	"""
	if not column_widths:
		return

	for idx, width in enumerate(column_widths, start=1):
		if width:
			ws.column_dimensions[get_column_letter(idx)].width = width


def _apply_dimension_styles(
	ws,
	column_styles: dict,
	row_styles: dict,
	cell_styles: dict,
) -> bool:
	"""
	Apply styles to row/column dimensions when possible.

	Returns:
	    bool: True if cell-level styling is still needed, False if dimension styling was used.
	"""
	has_styles = bool(column_styles or row_styles or cell_styles)

	if not has_styles or cell_styles:
		return True

	# Only row styles - apply to row dimensions
	if row_styles and not column_styles:
		for row_idx, style in row_styles.items():
			_apply_style(ws.row_dimensions[row_idx + 1], style)
		return False

	# Only column styles - apply to column dimensions
	if column_styles and not row_styles:
		for col_idx, style in column_styles.items():
			_apply_style(ws.column_dimensions[get_column_letter(col_idx + 1)], style)
		return False

	return True


def _apply_style(target, style: dict) -> None:
	"""
	Apply style properties to a cell or dimension object.
	"""
	if font := style.get("font"):
		target.font = font
	if fill := style.get("fill"):
		target.fill = fill
	if alignment := style.get("alignment"):
		target.alignment = alignment
	if border := style.get("border"):
		target.border = border
	if number_format := style.get("number_format"):
		target.number_format = number_format


def _write_data_rows(
	ws,
	data: list[list[Any]],
	sheet_name: str,
	styles: dict | None = None,
) -> None:
	"""
	Write all data rows to the worksheet with appropriate styling.
	"""
	# Extract style configurations
	column_styles = styles.get("column_styles") or {}
	row_styles = styles.get("row_styles") or {}
	cell_styles = styles.get("cell_styles") or {}

	# Determine styling mode
	has_styles = bool(column_styles or row_styles or cell_styles)
	use_cell_styling = _apply_dimension_styles(ws, column_styles, row_styles, cell_styles)

	# Determine if HTML handling is needed
	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}

	for row_idx, row in enumerate(data):
		row_style = row_styles.get(row_idx) or {} if has_styles else {}

		excel_row = _build_excel_row(
			ws=ws,
			row=row,
			row_idx=row_idx,
			row_style=row_style,
			handle_html_content=handle_html_content,
			has_styles=has_styles,
			use_cell_styling=use_cell_styling,
			column_styles=column_styles,
			cell_styles=cell_styles,
		)

		ws.append(excel_row)


def _build_excel_row(
	ws,
	row: list,
	row_idx: int,
	row_style: dict,
	handle_html_content: bool,
	has_styles: bool,
	use_cell_styling: bool,
	column_styles: dict,
	cell_styles: dict,
) -> list:
	"""
	Build a single Excel row with styled cells.
	"""
	excel_row = []

	for col_idx, value in enumerate(row):
		# Process cell value
		value = _process_cell_value(value, handle_html_content)

		# Create cell
		cell = WriteOnlyCell(ws, value=value)

		# Apply styling if needed
		if has_styles and use_cell_styling:
			_apply_cell_style(
				cell=cell,
				row_idx=row_idx,
				col_idx=col_idx,
				row_style=row_style,
				column_styles=column_styles,
				cell_styles=cell_styles,
			)

		excel_row.append(cell)

	return excel_row


def _process_cell_value(value: Any, handle_html_content: bool) -> Any:
	"""
	Process and sanitize cell value.
	"""
	if isinstance(value, str):
		if handle_html_content:
			value = handle_html(value)
		value = ILLEGAL_CHARACTERS_RE.sub("", value)

	return value


def _apply_cell_style(
	cell,
	row_idx: int,
	col_idx: int,
	row_style: dict,
	column_styles: dict,
	cell_styles: dict,
) -> None:
	"""
	Apply merged styles to a cell (column < row < cell priority).
	"""
	cell_style = cell_styles.get((row_idx, col_idx)) or {}
	col_style = column_styles.get(col_idx) or {}

	# Skip if no styles to apply
	if not (cell_style or col_style or row_style):
		return

	# Merge styles with priority: column < row < cell
	merged_style = {}

	if col_style:
		merged_style.update(col_style)
	if row_style:
		merged_style.update(row_style)
	if cell_style:
		merged_style.update(cell_style)

	_apply_style(cell, merged_style)


### Utils ###
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
