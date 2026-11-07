# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import re
from io import BytesIO

import openpyxl
import xlrd
from openpyxl import load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

import frappe
from frappe.utils.csvutils import FORMULA_TRIGGER_CHARS
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


# return xlsx file object
def make_xlsx(data, sheet_name, wb=None, column_widths=None):
	column_widths = column_widths or []
	if wb is None:
		wb = openpyxl.Workbook(write_only=True)

	sheet_name_sanitized = INVALID_TITLE_REGEX.sub(" ", sheet_name)
	ws = wb.create_sheet(sheet_name_sanitized, 0)

<<<<<<< HEAD
=======
		wb = xlsxwriter.Workbook(xlsx_file, options)
		created_wb = True

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

	# time / duration values need an explicit number format, otherwise Excel shows raw day fractions
	excel_time_format = XLSXStyleBuilder.get_time_format()

	@functools.cache
	def get_time_cell_format(style_ids: tuple[int, ...], num_format: str) -> Format:
		style = dict(resolve_style_ids(style_ids))
		style.setdefault("num_format", num_format)
		return wb.add_format(style)

	# set column widths
>>>>>>> 4abfa99 (fix(xlsx): apply number format to time and timedelta values in Excel export)
	for i, column_width in enumerate(column_widths):
		if column_width:
			ws.column_dimensions[get_column_letter(i + 1)].width = column_width

	row1 = ws.row_dimensions[1]
	row1.font = Font(name="Calibri", bold=True)

	date_format, time_format = get_excel_date_format()

<<<<<<< HEAD
	for row in data:
		clean_row = []
		for item in row:
			if isinstance(item, str) and (sheet_name not in ["Data Import Template", "Data Export"]):
				value = handle_html(item)
=======
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

	# quick access for hot loop
	handle_html_content = sheet_name not in {"Data Import Template", "Data Export"}
	illegal_chars_search = ILLEGAL_CHARACTERS_RE.search
	illegal_chars_sub = ILLEGAL_CHARACTERS_RE.sub

	write = ws.write
	write_string = ws.write_string
	has_cell_formats = bool(cell_formats)
	get_cell_format = cell_formats.get

	for row_idx, row in enumerate(data):
		for col_idx, value in enumerate(row):
			is_formula_like = False

			if isinstance(value, str):
				if handle_html_content:
					value = handle_html(value)

				if illegal_chars_search(value):
					value = illegal_chars_sub("", value)

				is_formula_like = value.startswith(FORMULA_TRIGGER_CHARS)

			cell_format = get_cell_format((row_idx, col_idx)) if has_cell_formats else None

			if isinstance(value, datetime.time | datetime.timedelta):
				cell_format = get_time_cell_format(
					col_style_ids.get(col_idx, ())
					+ row_style_ids.get(row_idx, ())
					+ cell_style_ids.get((row_idx, col_idx), ()),
					"[h]:mm:ss" if isinstance(value, datetime.timedelta) else excel_time_format,
				)

			if is_formula_like:
				# force literal text so the cell isn't parsed as a formula
				write_string(row_idx, col_idx, value, cell_format)
>>>>>>> 4abfa99 (fix(xlsx): apply number format to time and timedelta values in Excel export)
			else:
				value = item

			if isinstance(item, str) and next(ILLEGAL_CHARACTERS_RE.finditer(value), None):
				# Remove illegal characters from the string
				value = ILLEGAL_CHARACTERS_RE.sub("", value)

			if isinstance(value, datetime.date | datetime.datetime):
				number_format = date_format
				if isinstance(value, datetime.datetime):
					number_format = f"{date_format} {time_format}"

				cell = WriteOnlyCell(ws, value=value)
				cell.number_format = number_format
				clean_row.append(cell)
			elif isinstance(value, str) and value.startswith(FORMULA_TRIGGER_CHARS):
				# force literal text so the cell isn't parsed as a formula
				cell = WriteOnlyCell(ws, value=value)
				cell.data_type = "s"
				clean_row.append(cell)
			else:
				clean_row.append(value)

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


def read_xlsx_file_from_attached_file(file_url=None, fcontent=None, filepath=None, *, read_only=False):
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
	wb1 = load_workbook(filename=filename, data_only=True, read_only=read_only)
	ws1 = wb1.active
	for row in ws1.iter_rows():
		rows.append([cell.value for cell in row])
	if read_only:
		wb1.close()
	return rows


def read_xls_file_from_attached_file(content):
	book = xlrd.open_workbook(file_contents=content)
	sheets = book.sheets()
	sheet = sheets[0]
	return [sheet.row_values(i) for i in range(sheet.nrows)]


def build_xlsx_response(data, filename):
	from frappe.desk.utils import provide_binary_file

	provide_binary_file(filename, "xlsx", make_xlsx(data, filename).getvalue())
