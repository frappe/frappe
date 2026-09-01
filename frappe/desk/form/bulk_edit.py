# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Download and upload helpers for the in-grid bulk edit of child tables.

Child tables whose docfield has ``allow_bulk_edit`` set show Download and Upload
buttons under the grid. Both support CSV and Excel; Excel needs the server
because the desk bundle has no spreadsheet reader or writer.
"""

import base64
import datetime

import frappe
from frappe import _
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import (
	build_xlsx_response,
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

SUPPORTED_EXTENSIONS = ("csv", "xlsx", "xls")

# guards a whole spreadsheet being posted back as a form field
MAX_TEMPLATE_ROWS = 10000


@frappe.whitelist()
def download_bulk_edit_template(doctype: str, title: str, data: str, file_type: str = "Excel"):
	"""Send the grid's bulk edit template back as an Excel file.

	The sheet is built on the client and posted here because the grid may hold
	unsaved rows that are not in the database yet. CSV is written in the browser
	and never reaches this method.
	"""
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

	rows = [row if isinstance(row, list) else [row] for row in rows]

	if file_type != "Excel":
		frappe.throw(_("{0} is not a supported file type").format(file_type), title=_("Download Failed"))

	build_xlsx_response(rows, title)


@frappe.whitelist()
def parse_bulk_edit_file(doctype: str, filename: str, dataurl: str) -> list[list[str]]:
	"""Read an uploaded CSV, XLSX or XLS file into a list of rows of strings.

	Values are stringified so that the grid can apply the same per-fieldtype
	formatters regardless of which format the row came from — a spreadsheet
	hands back real numbers and datetimes where a CSV hands back text.
	"""
	if not frappe.has_permission(doctype, "write"):
		raise frappe.PermissionError

	extension = get_extension(filename)
	if extension not in SUPPORTED_EXTENSIONS:
		frappe.throw(
			_("File must be of type {0}").format(", ".join(f".{e}" for e in SUPPORTED_EXTENSIONS)),
			title=_("Invalid File"),
		)

	content = decode_dataurl(dataurl)

	if extension == "csv":
		rows = read_csv_content(content)
	elif extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	else:
		rows = read_xls_file_from_attached_file(content)

	return [[stringify(value) for value in row] for row in (rows or [])]


@frappe.whitelist()
def get_invalid_link_values(doctype: str, values_by_doctype: str) -> dict[str, list[str]]:
	"""Check which Link column values in the bulk edit preview don't exist.

	Batched by target doctype so the grid can validate every mapped Link column in one call.

	:param doctype: doctype of the form the grid belongs to, for the permission check
	:param values_by_doctype: JSON ``{linked_doctype: [distinct values]}``
	"""
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
	"""Return the bytes carried by a ``data:...;base64,<payload>`` URL."""
	if not dataurl:
		frappe.throw(_("No file content received"), title=_("Invalid File"))

	payload = dataurl.split(",", 1)[-1]

	try:
		return base64.b64decode(payload)
	except Exception:
		frappe.throw(_("Could not read the uploaded file"), title=_("Invalid File"))


def stringify(value) -> str:
	"""Render one spreadsheet cell as text the grid can hand to a field.

	Dates are written in system format. A spreadsheet has no date-only type, so a
	date cell always reads back as a datetime, and guessing which of the two the
	column meant would get it wrong either way. The grid knows the fieldtype and
	trims the time itself; a CSV, by contrast, still carries the user-format date
	string it was exported with, which the grid also still understands.
	"""
	if value is None:
		return ""

	if isinstance(value, bool):
		return "1" if value else "0"

	# datetime is a subclass of date, so it has to be checked first
	if isinstance(value, datetime.datetime):
		return value.strftime("%Y-%m-%d %H:%M:%S")

	if isinstance(value, datetime.date):
		return value.strftime("%Y-%m-%d")

	if isinstance(value, datetime.time):
		return value.strftime("%H:%M:%S")

	# openpyxl reads every number as a float; 3.0 should not become "3.0" in a Data field
	if isinstance(value, float) and value.is_integer():
		return str(int(value))

	return str(value)
