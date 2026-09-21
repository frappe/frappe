# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import datetime
import html

import frappe
from frappe import _
from frappe.core.doctype.data_import.importer import Row, get_df_for_column_header, get_item_at_index
from frappe.model import get_permitted_fields, no_value_fields, table_fields
from frappe.utils import cstr, get_user_date_format, get_user_time_format, strip_html
from frappe.utils.caching import request_cache
from frappe.utils.csvutils import get_csv_content_from_google_sheets, read_csv_content
from frappe.utils.dateutils import dateformats
from frappe.utils.xlsxutils import (
	build_xlsx_response,
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

SUPPORTED_EXTENSIONS = ("csv", "xlsx", "xls")

MAX_TEMPLATE_ROWS = 10000

MAX_IMPORT_ROWS = 5000


@frappe.whitelist(methods=["POST"])
def download_template(doctype: str, title: str, data: str, file_type: str = "Excel"):
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError

	rows = frappe.parse_json(data)
	if not isinstance(rows, list):
		frappe.throw(_("Invalid template data"), title=_("Download Failed"))

	if len(rows) - 1 > MAX_TEMPLATE_ROWS:
		frappe.throw(
			_("Cannot download more than {0} rows.").format(MAX_TEMPLATE_ROWS),
			title=_("Download Failed"),
		)

	if file_type != "Excel":
		frappe.throw(_("{0} is not a supported file type").format(file_type), title=_("Download Failed"))

	rows = [row if isinstance(row, list) else [row] for row in rows]
	build_xlsx_response(rows, title)


@frappe.whitelist(methods=["POST"])
def parse_file(
	doctype: str, filename: str | None = None, dataurl: str | None = None, file_url: str | None = None
) -> list[list[str]]:
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	file_doc = None
	if file_url:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_doc.check_permission("read")
		filename = filename or file_doc.file_name

	extension = get_extension(filename)
	if extension not in SUPPORTED_EXTENSIONS:
		frappe.throw(
			_("File must be of type {0}").format(", ".join(f".{e}" for e in SUPPORTED_EXTENSIONS)),
			title=_("Invalid File"),
		)

	content = file_doc.get_content() if file_doc else decode_dataurl(dataurl)

	if extension == "csv":
		rows = read_csv_content(content)
	elif extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	else:
		rows = read_xls_file_from_attached_file(content)

	return [[stringify(value) for value in row] for row in (rows or [])]


@frappe.whitelist(methods=["POST"])
def parse_google_sheet(doctype: str, url: str) -> list[list[str]]:
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	content = get_csv_content_from_google_sheets(url)
	rows = read_csv_content(content)

	return [[stringify(value) for value in row] for row in (rows or [])]


@frappe.whitelist(methods=["POST"])
def get_column_map(doctype: str, fieldname: str, headers: str) -> dict[int, str]:
	child_doctype = get_child_doctype(doctype, fieldname)
	writable = get_writable_fields(doctype, child_doctype)

	column_map = {}
	for i, header in enumerate(frappe.parse_json(headers) or []):
		header = cstr(header).strip()
		if not header:
			continue
		df = get_df_for_column_header(child_doctype, header)
		if df and df.fieldname in writable:
			column_map[i] = df.fieldname

	return column_map


@frappe.whitelist(methods=["POST"])
def validate_rows(doctype: str, fieldname: str, headers: str, rows: str, column_map: str) -> list[dict]:
	child_doctype = get_child_doctype(doctype, fieldname)
	rows = frappe.parse_json(rows)
	if len(rows) > MAX_IMPORT_ROWS:
		frappe.throw(_("Cannot import table with more than {0} rows.").format(MAX_IMPORT_ROWS))

	writable = get_writable_fields(doctype, child_doctype)
	meta = frappe.get_meta(child_doctype)
	date_format = dateformats.get(get_user_date_format(), "%Y-%m-%d")

	columns = [
		frappe._dict(
			index=int(i), column_number=int(i) + 1, df=meta.get_field(field), date_format=date_format
		)
		for i, field in frappe.parse_json(column_map).items()
		if field in writable and meta.get_field(field)
	]
	header = frappe._dict(columns=frappe.parse_json(headers))

	warnings = []
	for index, data in enumerate(rows):
		row = GridImportRow(index, data, child_doctype, header, import_type=None)
		for col in columns:
			value = cstr(get_item_at_index(data, col.index)).strip()
			if not value:
				continue
			seen = len(row.warnings)
			row.validate_value(value, col)
			for warning in row.warnings[seen:]:
				warning["col"] = col.index

		warnings.extend(
			{
				"row": index,
				"col": warning.get("col"),
				"blocking": warning.get("col") is not None,
				"message": html.unescape(strip_html(warning["message"])),
			}
			for warning in row.warnings
		)

	return warnings


class GridImportRow(Row):
	def link_exists(self, value, df):
		return not can_read(df.options, frappe.session.user) or super().link_exists(value, df)

	def validate_value(self, value, col):
		if col.df.fieldtype == "Duration" and value.isdigit():
			return value
		return super().validate_value(value, col)

	def get_date(self, value, column):
		parsed = parse_datetime(value, (column.date_format, "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"))
		return parsed.date() if isinstance(parsed, datetime.datetime) else parsed

	def get_datetime(self, value, column):
		time_format = get_user_time_format().replace("HH", "%H").replace("mm", "%M").replace("ss", "%S")
		return parse_datetime(value, (f"{column.date_format} {time_format}", "%Y-%m-%d %H:%M:%S"))


@request_cache
def can_read(doctype: str, user: str) -> bool:
	return frappe.has_permission(doctype, "read", user=user)


def parse_datetime(value: str, formats) -> datetime.datetime | str:
	for date_format in formats:
		try:
			return datetime.datetime.strptime(value, date_format)
		except ValueError:
			continue
	return value


def get_child_doctype(doctype: str, fieldname: str) -> str:
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	table_df = frappe.get_meta(doctype).get_field(fieldname)
	if not table_df or table_df.fieldtype not in table_fields:
		frappe.throw(_("{0} is not a table field").format(frappe.bold(fieldname)))

	return table_df.options


def get_writable_fields(doctype: str, child_doctype: str) -> set[str]:
	permitted = set(get_permitted_fields(child_doctype, parenttype=doctype, permission_type="write"))

	writable = {
		df.fieldname
		for df in frappe.get_meta(child_doctype).fields
		if df.fieldtype not in no_value_fields and not df.is_virtual and df.fieldname in permitted
	}
	writable.add("name")
	return writable


def get_extension(filename: str) -> str:
	return (filename or "").rsplit(".", 1)[-1].lower()


def decode_dataurl(dataurl: str) -> bytes:
	if not dataurl:
		frappe.throw(_("No file content received"), title=_("Invalid File"))

	payload = dataurl.split(",", 1)[-1]

	try:
		return base64.b64decode(payload)
	except Exception:
		frappe.throw(_("Could not read the uploaded file"), title=_("Invalid File"))


def stringify(value) -> str:
	if value is None:
		return ""

	if isinstance(value, bool):
		return "1" if value else "0"

	if isinstance(value, datetime.datetime):
		return value.strftime("%Y-%m-%d %H:%M:%S")

	if isinstance(value, datetime.date):
		return value.strftime("%Y-%m-%d")

	if isinstance(value, datetime.time):
		return value.strftime("%H:%M:%S")

	if isinstance(value, float) and value.is_integer():
		return str(int(value))

	return str(value)
