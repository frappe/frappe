# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

EXPORTED_REPORT_FOLDER_PATH = "Home/Exported Reports"


def validate_route_conflict(doctype, name):
	"""
	Raises exception if name clashes with routes from other documents for /app routing
	"""

	if frappe.flags.in_migrate:
		return

	all_names = []
	for _doctype in ["Page", "Workspace", "DocType"]:
		all_names.extend(
			[slug(d) for d in frappe.get_all(_doctype, pluck="name") if (doctype != _doctype and d != name)]
		)

	if slug(name) in all_names:
		frappe.msgprint(frappe._("Name already taken, please set a new name"))
		raise frappe.NameError


def slug(name):
	return name.lower().replace(" ", "-")


def pop_csv_params(form_dict):
	"""Pop csv params from form_dict and return them as a dict."""
	from csv import QUOTE_NONNUMERIC

	from frappe.utils.data import cint, cstr

	return {
		"delimiter": cstr(form_dict.pop("csv_delimiter", ","))[0],
		"quoting": cint(form_dict.pop("csv_quoting", QUOTE_NONNUMERIC)),
	}


def get_csv_bytes(data: list[list], csv_params: dict) -> bytes:
	"""Convert data to csv bytes."""
	from csv import writer
	from io import StringIO

	file = StringIO()
	csv_writer = writer(file, **csv_params)
	csv_writer.writerows(data)

	return file.getvalue().encode("utf-8")


def provide_binary_file(filename: str, extension: str, content: bytes) -> None:
	"""Provide a binary file to the client."""
	from frappe import _

	frappe.response["type"] = "binary"
	frappe.response["filecontent"] = content
	frappe.response["filename"] = f"{_(filename)}.{extension}"


def send_report_email(
	user_email: str, report_name: str, file_extension: str, content: bytes, attached_to_name: str
):
	create_exported_report_folder_if_not_exists()
	_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{report_name}.{file_extension}",
			"attached_to_doctype": "Report",
			"attached_to_name": attached_to_name,
			"content": content,
			"is_private": 1,
			"folder": EXPORTED_REPORT_FOLDER_PATH,
		}
	)
	_file.save(ignore_permissions=True)

	file_url = frappe.utils.get_url(_file.get_url())
	file_retention_hours = frappe.get_system_settings("delete_background_exported_reports_after") or 48

	frappe.sendmail(
		recipients=[user_email],
		subject=frappe._("Your exported report: {0}").format(report_name),
		message=frappe._(
			"The report you requested has been generated.<br><br>"
			"Click here to download:<br>"
			"<a href='{0}'>{0}</a><br><br>"
			"This link will expire in {1} hours."
		).format(file_url, file_retention_hours),
		now=True,
	)


def delete_old_exported_report_files():
	file_retention_hours = frappe.get_system_settings("delete_background_exported_reports_after") or 48

	cutoff = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-file_retention_hours)
	old_files = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Report",
			"creation": ("<", cutoff),
			"folder": EXPORTED_REPORT_FOLDER_PATH,
		},
		pluck="name",
	)

	for file_name in old_files:
		try:
			frappe.delete_doc("File", file_name)
		except Exception:
			frappe.log_error(f"Failed to delete old report file {file_name}")


def create_exported_report_folder_if_not_exists():
	parent_folder, folder_name = EXPORTED_REPORT_FOLDER_PATH.split("/")
	folder = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": folder_name,
			"is_folder": 1,
			"folder": parent_folder,
			"is_private": 1,
		}
	)
	folder.insert(ignore_permissions=True, ignore_if_duplicate=True)
