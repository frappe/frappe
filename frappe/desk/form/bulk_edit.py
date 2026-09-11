# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import datetime

import frappe
from frappe import _
from frappe.core.doctype.data_import.importer import get_df_for_column_header
from frappe.model import no_value_fields, table_fields
from frappe.utils import cstr
from frappe.utils.csvutils import get_csv_content_from_google_sheets, read_csv_content
from frappe.utils.xlsxutils import (
	build_xlsx_response,
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

SUPPORTED_EXTENSIONS = ("csv", "xlsx", "xls")

MAX_TEMPLATE_ROWS = 10000


@frappe.whitelist(methods=["POST"])
def download_bulk_edit_template(doctype: str, title: str, data: str, file_type: str = "Excel"):
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError

	rows = frappe.parse_json(data)
	if not isinstance(rows, list):
		frappe.throw(_("Invalid template data"), title=_("Download Failed"))

	if len(rows) > MAX_TEMPLATE_ROWS:
		frappe.throw(
			_("Cannot download more than {0} rows.").format(MAX_TEMPLATE_ROWS),
			title=_("Download Failed"),
		)

	if file_type != "Excel":
		frappe.throw(_("{0} is not a supported file type").format(file_type), title=_("Download Failed"))

	rows = [row if isinstance(row, list) else [row] for row in rows]
	build_xlsx_response(rows, title)


@frappe.whitelist(methods=["POST"])
def parse_bulk_edit_file(
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
def parse_bulk_edit_google_sheet(doctype: str, url: str) -> list[list[str]]:
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	content = get_csv_content_from_google_sheets(url)
	rows = read_csv_content(content)

	return [[stringify(value) for value in row] for row in (rows or [])]


@frappe.whitelist(methods=["POST"])
def get_bulk_edit_column_map(doctype: str, fieldname: str, headers: str) -> dict[int, str]:
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	table_df = frappe.get_meta(doctype).get_field(fieldname)
	if not table_df or table_df.fieldtype not in table_fields:
		frappe.throw(_("{0} is not a table field").format(frappe.bold(fieldname)))

	child_doctype = table_df.options

	writable = {
		df.fieldname
		for df in frappe.get_meta(child_doctype).fields
		if df.fieldtype not in no_value_fields and not df.read_only
	}
	writable.add("name")

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
def get_invalid_link_values(doctype: str, values_by_doctype: str) -> dict[str, list[str]]:
	if not frappe.has_permission(doctype, "read"):
		raise frappe.PermissionError

	values_by_doctype = frappe.parse_json(values_by_doctype)
	return {
		linked_doctype: [value for value in values if not frappe.db.exists(linked_doctype, value, cache=True)]
		for linked_doctype, values in values_by_doctype.items()
		if frappe.has_permission(linked_doctype, "read")
	}


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
