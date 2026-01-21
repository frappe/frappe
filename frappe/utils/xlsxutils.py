# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from io import BytesIO
from typing import Any, ClassVar, Literal

import openpyxl
import xlrd
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

import frappe
from frappe import _
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
	# Mapping of style property names to their openpyxl classes
	STYLE_CLASSES: ClassVar[dict] = {
		"font": Font,
		"fill": PatternFill,
		"alignment": Alignment,
		"number_format": str,
	}

	def __init__(self, metadata: XLSXMetadata):
		self.metadata = metadata

		self.styles = {}
		self.config = {
			"column_styles": {},
			"row_styles": {},
			"cell_styles": {},
		}

		self._register_default_highlight_styles()
		self._register_default_indent_styles()
		self._register_default_fieldtype_formats()

	### STYLE REGISTRATION ###
	def _register_default_highlight_styles(self):
		highlight_styles = {
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

		for name, style in highlight_styles.items():
			self.register_style(name, **style)

	def _register_default_indent_styles(self):
		if not self.metadata.max_indent_level:
			return

		for indent in range(self.metadata.max_indent_level + 1):
			self.register_style(f"indent_{indent}", alignment={"indent": indent * 2, "horizontal": "left"})

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

	def register_style(self, name: str, **kwargs):
		"""
		Register a named style for reuse across multiple cells/rows/columns.

		Args:
			name: Unique name for this style
			font: Font configuration (dict or Font object)
			fill: Fill configuration (dict or PatternFill object)
			number_format: Excel number format string
			alignment: Alignment configuration (dict or Alignment object)
		"""
		style = frappe._dict()

		# Handle style objects with automatic instantiation
		for prop_name, style_class in self.STYLE_CLASSES.items():
			if config := kwargs.get(prop_name):
				style[prop_name] = style_class(**config) if isinstance(config, dict) else config

		self.styles[name] = style

		return self

	### STYLE APPLICATION ###
	def style_column(self, col_idx: int, style_name: str):
		if style := self.styles.get(style_name):
			self.config["column_styles"][col_idx] = style

		return self

	def style_row(self, row_idx: int, style_name: str):
		if style := self.styles.get(style_name):
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
		if style_name and (style := self.styles.get(style_name)):
			cell_style.update(style)

		# Apply indent style (overrides alignment from named style)
		if indent is not None and (style := self.styles.get(f"indent_{indent}")):
			cell_style["alignment"] = style["alignment"]

		return self

	def build(self) -> frappe._dict:
		"""
		Merge styles into a unified cell_styles dictionary.

		Openpyxl overrides a cell style if more than one style is applied to it,
		such as when both column and row styles are present. This function merges
		the styles for such cells to ensure full formatting is applied correctly.

		Merge priority (lowest to highest):
			1. Column styles
			2. Row styles
			3. Cell styles (highest priority, overrides all)

		Returns:
			frappe._dict: The updated config with resolved cell_styles that include
						  merged formatting from row and column styles where applicable.
		"""
		cell_styles = self.config["cell_styles"]
		row_styles = self.config["row_styles"]
		col_styles = self.config["column_styles"]

		if not (cell_styles or row_styles or col_styles):
			return self.config

		# If only row OR only col exists and no cell_styles, nothing to resolve
		if not cell_styles and (bool(row_styles) ^ bool(col_styles)):
			return self.config

		styled_rows = frozenset(row_styles.keys())
		styled_cols = frozenset(col_styles.keys())

		# Process row x col intersections (positions with both row and col styles)
		if row_styles and col_styles:
			for r in styled_rows:
				row_style = row_styles[r]

				for c in styled_cols:
					pos = (r, c)
					# Merge: col_style < row_style < cell_style
					merged = {**col_styles[c], **row_style}

					if pos in cell_styles:
						cell_styles[pos] = {**merged, **cell_styles[pos]}
					else:
						cell_styles[pos] = merged

		# Process existing cell_styles that weren't in the row x col intersection
		for pos, cell_style in list(cell_styles.items()):
			r, c = pos
			in_styled_row = r in styled_rows
			in_styled_col = c in styled_cols

			# Skip if both (already handled in step 1) or neither (no merge needed)
			if in_styled_row == in_styled_col:
				continue

			if in_styled_row:
				cell_styles[pos] = {**row_styles[r], **cell_style}
			else:
				cell_styles[pos] = {**col_styles[c], **cell_style}

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

		self.apply_default_fieldtype_formats()

		return self

	def style_header(self):
		return self.style_row(self.metadata.header_index, "header")

	def style_filters(self):
		for row_idx in range(0, self.metadata.header_index):
			self.style_cell(row_idx, 0, style_name="filter_label")

		return self

	def apply_indentations(self, column: int):
		for idx, row in self.metadata.row_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(idx, column, indent=row["indent"])

		return self

	def style_total_row(self):
		return self.style_row(self.metadata.last_row_index, "total_row")

	def apply_default_fieldtype_formats(self):
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

		return self

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
	def get_number_format(fieldtype: Literal["Float", "Percent"]) -> str:
		from frappe.locale import get_number_format as _get_format

		number_format = _get_format()
		thousands_sep = number_format.thousands_separator
		decimal_sep = number_format.decimal_separator
		precision = number_format.precision

		if fieldtype in ("Float", "Percent"):
			precision = cint(frappe.db.get_default("float_precision")) or precision
			format_str = XLSXStyleBuilder._build_number_format(thousands_sep, decimal_sep, precision)
			return f'{format_str}"%" ' if fieldtype == "Percent" else format_str

		return "General"

	@staticmethod
	def _build_number_format(thousands_sep: str, decimal_sep: str, precision: int = 0) -> str:
		integer_part = "#,##0" if thousands_sep else "#0"
		decimal_part = (decimal_sep + "0" * precision) if precision > 0 else ""

		return f"{integer_part}{decimal_part}"

	#### Excel Color Utils ####
	@staticmethod
	@frappe.request_cache
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

	def _apply_style(target, style: dict) -> None:
		if font := style.get("font"):
			target.font = font
		if border := style.get("border"):
			target.border = border
		if fill := style.get("fill"):
			target.fill = fill
		if alignment := style.get("alignment"):
			target.alignment = alignment
		if number_format := style.get("number_format"):
			target.number_format = number_format

	column_widths = column_widths or []
	styles = styles or {}

	# Create workbook and worksheet
	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	ws = wb.create_sheet(INVALID_TITLE_REGEX.sub(" ", sheet_name), 0)

	# Apply styles
	if column_styles := styles.get("column_styles"):
		for col_idx, style in column_styles.items():
			_apply_style(ws.column_dimensions[get_column_letter(col_idx + 1)], style)

	for idx, width in enumerate(column_widths, start=1):
		if width:
			ws.column_dimensions[get_column_letter(idx)].width = width

	if row_styles := styles.get("row_styles"):
		for row_idx, style in row_styles.items():
			_apply_style(ws.row_dimensions[row_idx + 1], style)

	cell_styles = styles.get("cell_styles")

	# Determine if HTML handling is needed
	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}

	for row_idx, row in enumerate(data):
		excel_row = []

		for col_idx, value in enumerate(row):
			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			cell = WriteOnlyCell(ws, value=value)

			if cell_styles and (style := cell_styles.get((row_idx, col_idx))):
				_apply_style(cell, style)

			excel_row.append(cell)

		ws.append(excel_row)

	xlsx_file = BytesIO()
	wb.save(xlsx_file)
	return xlsx_file


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
