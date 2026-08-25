# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import datetime
import json

import frappe
from frappe.desk.form.bulk_edit import (
	MAX_TEMPLATE_ROWS,
	download_bulk_edit_template,
	parse_bulk_edit_file,
	stringify,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.xlsxutils import make_xlsx

HEADER_ROWS = [
	["Bulk Edit Roles"],
	["Role", "Description"],
	["role", "description"],
	["", ""],
	["The file format is case sensitive"],
	["Do not edit headers which are preset in the template"],
	["------"],
]


def as_dataurl(content: bytes) -> str:
	return "data:application/octet-stream;base64," + base64.b64encode(content).decode()


class TestBulkEdit(IntegrationTestCase):
	def test_download_returns_an_xlsx_binary(self):
		rows = [*HEADER_ROWS, ["System Manager", "everything"]]
		download_bulk_edit_template("User", "Roles", json.dumps(rows))

		self.assertEqual(frappe.response["type"], "binary")
		self.assertEqual(frappe.response["filename"], "Roles.xlsx")
		# xlsx is a zip archive
		self.assertTrue(frappe.response["filecontent"].startswith(b"PK"))

	def test_download_rejects_csv(self):
		# csv is written in the browser and must never reach the server
		with self.assertRaises(frappe.ValidationError):
			download_bulk_edit_template("User", "Roles", json.dumps(HEADER_ROWS), file_type="CSV")

	def test_download_rejects_oversized_template(self):
		rows = [["x"]] * (MAX_TEMPLATE_ROWS + 1)
		with self.assertRaises(frappe.ValidationError):
			download_bulk_edit_template("User", "Roles", json.dumps(rows))

	def test_xlsx_and_csv_uploads_agree(self):
		rows = [*HEADER_ROWS, ["System Manager", "everything"]]

		xlsx = parse_bulk_edit_file(
			"User", "roles.xlsx", as_dataurl(make_xlsx(rows, "Roles").getvalue())
		)
		csv_text = "\n".join(",".join(f'"{cell}"' for cell in row) for row in rows)
		csv = parse_bulk_edit_file("User", "roles.csv", as_dataurl(csv_text.encode()))

		# the xlsx sheet is padded to a rectangle, the csv is not; the rows that
		# carry data have to match cell for cell
		self.assertEqual(xlsx[2][:2], ["role", "description"])
		self.assertEqual(csv[2][:2], ["role", "description"])
		self.assertEqual(xlsx[-1][:2], ["System Manager", "everything"])
		self.assertEqual(csv[-1][:2], ["System Manager", "everything"])

	def test_upload_rejects_unsupported_extension(self):
		with self.assertRaises(frappe.ValidationError):
			parse_bulk_edit_file("User", "roles.txt", as_dataurl(b"role\n"))

	def test_upload_rejects_empty_content(self):
		with self.assertRaises(frappe.ValidationError):
			parse_bulk_edit_file("User", "roles.csv", "")

	def test_dates_round_trip_through_a_spreadsheet(self):
		# a spreadsheet has no date-only type, so a date cell reads back as a
		# datetime; it must still come out in system format for the grid to trim
		rows = [*HEADER_ROWS, ["System Manager", datetime.date(2026, 8, 25)]]
		parsed = parse_bulk_edit_file(
			"User", "roles.xlsx", as_dataurl(make_xlsx(rows, "Roles").getvalue())
		)
		self.assertEqual(parsed[-1][1], "2026-08-25 00:00:00")

	def test_stringify_renders_cells_for_the_grid(self):
		self.assertEqual(stringify(None), "")
		self.assertEqual(stringify(True), "1")
		self.assertEqual(stringify(False), "0")
		self.assertEqual(stringify(datetime.date(2026, 8, 25)), "2026-08-25")
		self.assertEqual(stringify(datetime.datetime(2026, 8, 25, 10, 30)), "2026-08-25 10:30:00")
		self.assertEqual(stringify(datetime.time(10, 30)), "10:30:00")
		# openpyxl reads every number as a float
		self.assertEqual(stringify(3.0), "3")
		self.assertEqual(stringify(3.5), "3.5")

	def test_permission_is_checked_against_the_parent_doctype(self):
		self.assertRaises(
			frappe.PermissionError,
			lambda: self.with_user("Guest", download_bulk_edit_template, "User", "Roles", "[]"),
		)
		self.assertRaises(
			frappe.PermissionError,
			lambda: self.with_user(
				"Guest", parse_bulk_edit_file, "User", "roles.csv", as_dataurl(b"role\n")
			),
		)

	def with_user(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")
