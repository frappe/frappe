# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import functools
import re
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
from frappe.core.utils import html2text
from frappe.utils import cint
from frappe.utils.html_utils import unescape_html

ILLEGAL_CHARACTERS_RE = re.compile(
	r"[\000-\010]|[\013-\014]|[\016-\037]|\uFEFF|\uFFFE|\uFFFF|[\uD800-\uDFFF]"
)


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
	applied_filters_map: dict[int, list | dict] = dataclass_field(default_factory=dict)

	header_index: int = 0
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

	def get_last_row_index(self) -> int | None:
		if self.row_map:
			return max(self.row_map.keys())

		return None


class XLSXStyleBuilder:
	def __init__(self, metadata: XLSXMetadata):
		self.metadata = metadata

		# Index -> style ID
		self.styles: list[dict] = []

		self.config = {
			"column_styles": {},
			"row_styles": {},
			"cell_styles": {},
		}

		self._build_field_indexes()

		self._register_default_highlight_styles()
		self._register_default_indent_styles()
		self._register_default_fieldtype_formats()

	### POST INIT METHODS ###
	def _build_field_indexes(self):
		self.currency_fields = {}

		self.currency_field_exists = any(
			col.get("fieldtype") == "Currency" for col in self.metadata.column_map.values()
		)

		if self.currency_field_exists:
			for col_idx, col in self.metadata.column_map.items():
				if col.get("fieldtype") == "Currency":
					self.currency_fields[col_idx] = col

		# column fieldname -> idx mapping
		self.column_fieldname_to_index = {
			col.get("fieldname"): idx for idx, col in self.metadata.column_map.items() if col.get("fieldname")
		}

	### STYLE REGISTRATION ###
	def _register_default_highlight_styles(self):
		self._header_style = self.register_style({"bold": True, "font_size": 13})
		self._total_row_style = self.register_style({"bold": True, "font_size": 12})
		self._filter_label_style = self.register_style({"bold": True})

	def _register_default_indent_styles(self):
		self._indent_styles: dict[int, int] = {}  # indent_level -> style_id

		for indent in range(self.metadata.max_indent_level + 1):
			self._indent_styles[indent] = self.register_style({"align": "left", "indent": indent * 2})

	def _register_default_fieldtype_formats(self):
		self._currency_formats: dict[str, int] = {}

		self._default_fieldtype_formats: dict[str, int] = {
			"Float": self.register_style({"num_format": self.get_number_format("Float")}),
			"Percent": self.register_style({"num_format": self.get_number_format("Percent")}),
			"Date": self.register_style({"num_format": self.get_date_format()}),
			"Time": self.register_style({"num_format": self.get_time_format()}),
			"Datetime": self.register_style({"num_format": self.get_datetime_format()}),
		}

	def register_currency_format(self, currency: str) -> int | None:
		if currency in self._currency_formats:
			return self._currency_formats[currency]

		self._currency_formats[currency] = self.register_style(
			{"num_format": self.get_number_format("Currency", currency)}
		)

		return self._currency_formats[currency]

	def register_style(self, style: dict) -> int:
		"""
		Register a style and return its ID.

		Args:
			style: Dictionary of style properties

		Returns:
			int: Style ID (index in the registry)
		"""
		style_id = len(self.styles)
		self.styles.append(style)

		return style_id

	### STYLE APPLICATION ###
	def style_column(self, col_idx: int, style_id: int):
		if style_id is None:
			return self

		column_styles = self.config["column_styles"]

		if col_idx in column_styles:
			column_styles[col_idx].append(style_id)
		else:
			column_styles[col_idx] = [style_id]

		return self

	def style_row(self, row_idx: int, style_id: int):
		if style_id is None:
			return self

		row_styles = self.config["row_styles"]

		if row_idx in row_styles:
			row_styles[row_idx].append(style_id)
		else:
			row_styles[row_idx] = [style_id]

		return self

	def style_cell(self, row_idx: int, col_idx: int, style_id: int):
		if style_id is None:
			return self

		key = (row_idx, col_idx)
		cell_styles = self.config["cell_styles"]

		if key in cell_styles:
			cell_styles[key].append(style_id)
		else:
			cell_styles[key] = [style_id]

		return self

	def build(self) -> frappe._dict:
		"""
		Build final config with style registry and style ID references.

		Returns:
			frappe._dict: Config with style registry (list) and style ID mappings.
		"""
		self.config["styles"] = self.styles
		return self.config

	### UTILITY METHODS FOR STYLING ###
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
		return self.style_row(self.metadata.header_index, self._header_style)

	def style_filters(self):
		LABEL_COLUMN_INDEX = 0

		for row_idx in self.metadata.applied_filters_map.keys():
			self.style_cell(row_idx, LABEL_COLUMN_INDEX, self._filter_label_style)

		return self

	def apply_indentations(self, col_idx: int):
		for row_idx, row in self.metadata.row_map.items():
			if isinstance(row, dict) and "indent" in row:
				self.style_cell(row_idx, col_idx, self._indent_styles.get(row["indent"]))

		return self

	def style_total_row(self):
		return self.style_row(self.metadata.get_last_row_index(), self._total_row_style)

	def apply_default_fieldtype_formats(
		self, *, currency_formatting: bool = False, currency: str | dict | None = None
	):
		for idx, col in self.metadata.column_map.items():
			style_id = self._default_fieldtype_formats.get(col.get("fieldtype"))

			if style_id is not None:
				self.style_column(idx, style_id)

		if currency_formatting:
			self.apply_currency_fieldtype_formats(currency)

		return self

	def apply_currency_fieldtype_formats(self, currency: str | dict | None = None):
		if not self.currency_field_exists:
			return self

		# single currency for all currency fields
		if isinstance(currency, str):
			style_id = self.register_currency_format(currency)

			if style_id is not None:
				for col_idx in self.currency_fields:
					self.style_column(col_idx, style_id)

			return self

		mapped_columns: set[int] = set()

		# currency mapping per field (highest priority)
		if isinstance(currency, dict):
			for fieldname, code in currency.items():
				col_idx = self.column_fieldname_to_index.get(fieldname)
				if col_idx is None:
					continue

				style_id = self.register_currency_format(code)
				if style_id is not None:
					self.style_column(col_idx, style_id)
					mapped_columns.add(col_idx)

			# skip row-wise currency formatting
			if mapped_columns == set(self.currency_fields.keys()):
				return self

		# currency per row (fallback for unmapped fields)
		default_currency = frappe.db.get_default("currency")

		has_total_row = self.metadata.add_total_row
		last_row_index = self.metadata.get_last_row_index()
		ignore_visible_idx = self.metadata.ignore_visible_idx

		for row_idx, row in self.metadata.row_map.items():
			# currency format should not be applied to total row
			if row_idx == last_row_index and has_total_row and ignore_visible_idx:
				continue

			for col_idx, col in self.currency_fields.items():
				# skip columns already styled via mapping
				if col_idx in mapped_columns:
					continue

				curr = self.get_field_currency(col, row) or default_currency
				style_id = self.register_currency_format(curr)

				if style_id is not None:
					self.style_cell(row_idx, col_idx, style_id)

		return self

	### CURRENCY RESOLUTION ###
	def get_field_currency(self, df: dict, doc: dict | list) -> str | None:
		"""
		Get currency value for a field from document data.

		Args:
			df: Field definition with 'fieldname' and 'options'
			doc: Row data as dict or list

		Options format:
			- "currency_fieldname" -> direct field reference
			- "DocType:link_field:currency_field" -> fetch from linked document
		"""
		options = df.get("options")
		if not options or not doc:
			return None

		if ":" in options:
			return self._resolve_linked_currency(options, doc)

		return self._resolve_direct_currency(options, doc)

	def _resolve_linked_currency(self, options: str, doc: dict | list) -> str | None:
		parts = options.split(":")

		if len(parts) != 3:
			return None

		doctype, link_field, currency_field = parts

		if isinstance(doc, dict):
			docname = doc.get(link_field)
		else:
			link_idx = self.column_fieldname_to_index.get(link_field)
			docname = doc[link_idx] if link_idx is not None and link_idx < len(doc) else None

		if docname:
			return self._get_currency(doctype, docname, currency_field)

	def _resolve_direct_currency(self, options: str, doc: dict | list) -> str | None:
		if isinstance(doc, dict):
			return doc.get(options)

		currency_idx = self.column_fieldname_to_index.get(options)

		if currency_idx is not None:
			return doc[currency_idx]

	@staticmethod
	@frappe.request_cache
	def _get_currency(doctype: str, docname: str, fieldname: str) -> str | None:
		return frappe.get_value(doctype, docname, fieldname)

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

	### Format Getters ###
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


def get_default_xlsx_styles(
	columns: list[dict],
	data: list[list | dict],
	applied_filters: list[list] | None = None,
	*,
	filters: dict | None = None,
	has_total_row: bool = False,
	has_filters: bool = False,
	has_indentation: bool = False,
	apply_currency_format: bool = False,
	currency: str | dict | None = None,
	return_builder: bool = False,
) -> XLSXStyleBuilder | dict:
	"""
	Generate default XLSX styles for xlsx exports.

	Args:
		columns: Column definitions with keys: fieldname, fieldtype, label, options.
		data: Row data as list of dicts or lists (excluding header and filter rows).
		applied_filters: Filter rows to display at top of sheet. Each item is [label, value].
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
		return_builder: If True, returns XLSXStyleBuilder instance for further customization.
	"""
	applied_filters = applied_filters or []
	filters = filters or {}

	header_index = len(applied_filters) + 1 if applied_filters else 0

	applied_filters_map = dict(enumerate(applied_filters))
	column_map = dict(enumerate(columns))
	row_map = {header_index + 1 + idx: row for idx, row in enumerate(data)}

	max_indent_level = 0
	if has_indentation:
		for row in data:
			if isinstance(row, dict) and "indent" in row:
				max_indent_level = max(max_indent_level, row["indent"])

	metadata = XLSXMetadata(
		filters=filters,
		column_map=column_map,
		row_map=row_map,
		applied_filters_map=applied_filters_map,
		header_index=header_index,
		max_indent_level=max_indent_level,
		add_total_row=has_total_row,
		include_filters=has_filters,
		include_indentation=has_indentation,
	)

	builder = XLSXStyleBuilder(metadata)
	builder.apply_default_styles(currency_formatting=apply_currency_format, currency=currency)

	return builder if return_builder else builder.build()


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
		BytesIO: object containing the Excel file data, or None if wb was provided
	"""
	column_widths = column_widths or []
	styles = styles or {}

	# creating workbook
	xlsx_file = None
	created_wb = wb is None  # to know to close it later

	if created_wb:
		xlsx_file = BytesIO()
		wb = xlsxwriter.Workbook(
			xlsx_file, {"constant_memory": True, "default_date_format": XLSXStyleBuilder.get_date_format()}
		)

	# sanitize sheet name
	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.add_worksheet(sheet_name_sanitized[:31])

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

	@functools.cache
	def resolve_style_ids(style_ids: tuple[int, ...]) -> dict:
		"""
		Resolve a tuple of style IDs to a merged style dict.

		Note: Returns cached dict - do not mutate!
		"""
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
	for col_idx, ids in col_style_ids.items():
		ws.set_column(col_idx, col_idx, cell_format=get_format(ids))

	# row level styles
	for row_idx, ids in sorted(row_style_ids.items()):
		ws.set_row(row_idx, cell_format=get_format(ids))

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

	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}

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
