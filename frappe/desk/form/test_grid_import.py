# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import datetime
import json
from unittest.mock import patch

import frappe
from frappe.desk.form.grid_import import (
	MAX_IMPORT_ROWS,
	MAX_TEMPLATE_ROWS,
	GridImportRow,
	download_template,
	get_column_map,
	parse_file,
	parse_google_sheet,
	stringify,
	validate_rows,
)
from frappe.tests import IntegrationTestCase
from frappe.utils import format_datetime
from frappe.utils.xlsxutils import make_xlsx

HEADER = ["ID", "Role (role)"]


def as_dataurl(content: bytes) -> str:
	return "data:application/octet-stream;base64," + base64.b64encode(content).decode()


class TestGridImport(IntegrationTestCase):
	def test_download_returns_an_xlsx_binary(self):
		rows = [HEADER, ["", "System Manager"]]
		download_template("User", "Roles", json.dumps(rows))

		self.assertEqual(frappe.response["type"], "binary")
		self.assertEqual(frappe.response["filename"], "Roles.xlsx")
		self.assertTrue(frappe.response["filecontent"].startswith(b"PK"))

	def test_download_rejects_csv(self):
		with self.assertRaises(frappe.ValidationError):
			download_template("User", "Roles", json.dumps([HEADER]), file_type="CSV")

	def test_download_allows_the_full_row_limit(self):
		rows = [["Role"], *([["System Manager"]] * MAX_TEMPLATE_ROWS)]
		download_template("User", "Roles", json.dumps(rows))
		self.assertEqual(frappe.response["type"], "binary")

	def test_download_rejects_oversized_template(self):
		rows = [["Role"], *([["System Manager"]] * (MAX_TEMPLATE_ROWS + 1))]
		with self.assertRaises(frappe.ValidationError):
			download_template("User", "Roles", json.dumps(rows))

	def test_xlsx_and_csv_uploads_agree(self):
		rows = [HEADER, ["", "System Manager"]]

		xlsx = parse_file("User", "roles.xlsx", as_dataurl(make_xlsx(rows, "Roles").getvalue()))
		csv_text = "\n".join(",".join(f'"{cell}"' for cell in row) for row in rows)
		csv = parse_file("User", "roles.csv", as_dataurl(csv_text.encode()))

		self.assertEqual(xlsx, rows)
		self.assertEqual(csv, rows)

	def test_template_header_maps_back_to_its_fields(self):
		self.assertEqual(get_column_map("User", "roles", json.dumps(HEADER)), {0: "name", 1: "role"})

	def test_upload_rejects_unsupported_extension(self):
		with self.assertRaises(frappe.ValidationError):
			parse_file("User", "roles.txt", as_dataurl(b"role\n"))

	def test_upload_rejects_empty_content(self):
		with self.assertRaises(frappe.ValidationError):
			parse_file("User", "roles.csv", "")

	def test_dates_round_trip_through_a_spreadsheet(self):
		rows = [HEADER, [datetime.date(2026, 8, 25), "System Manager"]]
		parsed = parse_file("User", "roles.xlsx", as_dataurl(make_xlsx(rows, "Roles").getvalue()))
		self.assertEqual(parsed[1][0], "2026-08-25 00:00:00")

	def test_stringify_renders_cells_for_the_grid(self):
		self.assertEqual(stringify(None), "")
		self.assertEqual(stringify(True), "1")
		self.assertEqual(stringify(False), "0")
		self.assertEqual(stringify(datetime.date(2026, 8, 25)), "2026-08-25")
		self.assertEqual(stringify(datetime.datetime(2026, 8, 25, 10, 30)), "2026-08-25 10:30:00")
		self.assertEqual(stringify(datetime.time(10, 30)), "10:30:00")
		self.assertEqual(stringify(3.0), "3")
		self.assertEqual(stringify(3.5), "3.5")

	def test_datetime_cells_keep_their_time(self):
		rows = [["When"], [datetime.datetime(2026, 8, 25, 14, 5, 9)], [datetime.time(9, 30)]]
		parsed = parse_file("User", "times.xlsx", as_dataurl(make_xlsx(rows, "Times").getvalue()))
		self.assertEqual(parsed[1][0], "2026-08-25 14:05:09")
		self.assertEqual(parsed[2][0], "09:30:00")

	def test_column_map_matches_label_fieldname_and_template_header(self):
		headers = ["Number (phone)", "Is Primary Phone", "is_primary_mobile_no", "ID", "Nonsense", ""]
		column_map = get_column_map("Contact", "phone_nos", json.dumps(headers))

		self.assertEqual(
			column_map,
			{0: "phone", 1: "is_primary_phone", 2: "is_primary_mobile_no", 3: "name"},
		)

	def test_column_map_includes_read_only_fields(self):
		headers = ["Link Document Type (link_doctype)", "Link Title (link_title)"]
		column_map = get_column_map("Contact", "links", json.dumps(headers))

		self.assertEqual(column_map, {0: "link_doctype", 1: "link_title"})

	def test_column_map_rejects_a_non_table_field(self):
		with self.assertRaises(frappe.ValidationError):
			get_column_map("Contact", "first_name", json.dumps(["Number (phone)"]))

	def validate(self, doctype, fieldname, headers, rows, column_map):
		return validate_rows(
			doctype, fieldname, json.dumps(headers), json.dumps(rows), json.dumps(column_map)
		)

	def test_validate_rows_flags_missing_link_records(self):
		rows = [["User"], ["No Such DocType"], [""]]
		warnings = self.validate("Contact", "links", ["Link Document Type"], rows, {0: "link_doctype"})

		self.assertEqual(
			warnings,
			[
				{
					"row": 1,
					"col": 0,
					"blocking": True,
					"message": '"No Such DocType" is not a valid Link Document Type',
				}
			],
		)

	def test_validate_rows_flags_select_values_outside_the_options(self):
		rows = [["Monday"], ["Someday"]]
		warnings = self.validate("Assignment Rule", "assignment_days", ["Day"], rows, {0: "day"})

		self.assertEqual([(w["row"], w["col"]) for w in warnings], [(1, 0)])
		self.assertTrue(warnings[0]["message"].startswith('"Someday" is not valid. Allowed: Monday'))

	def test_validate_rows_checks_link_permission_once_per_doctype(self):
		frappe.local.request_cache.clear()
		rows = [["User"], ["No Such DocType"]] * 25

		with patch("frappe.has_permission", wraps=frappe.has_permission) as has_permission:
			warnings = self.validate("Contact", "links", ["Link Document Type"], rows, {0: "link_doctype"})

		doctype_checks = [c for c in has_permission.call_args_list if c.args[:1] == ("DocType",)]
		self.assertEqual(len(doctype_checks), 1)
		self.assertEqual(len(warnings), 25)

	def test_validate_rows_rejects_more_rows_than_an_import_allows(self):
		self.assertEqual(self.validate("Contact", "phone_nos", ["Number"], [["1"]] * MAX_IMPORT_ROWS, {}), [])
		with self.assertRaises(frappe.ValidationError):
			self.validate("Contact", "phone_nos", ["Number"], [["1"]] * (MAX_IMPORT_ROWS + 1), {})

	def test_validate_rows_reports_rows_of_the_wrong_width(self):
		warnings = self.validate("Contact", "phone_nos", ["Number", "Primary"], [["123"]], {0: "phone"})

		self.assertEqual(len(warnings), 1)
		self.assertEqual(warnings[0]["row"], 0)
		self.assertIsNone(warnings[0]["col"])
		self.assertFalse(warnings[0]["blocking"])

	def test_validate_rows_ignores_fields_that_cannot_be_imported(self):
		warnings = self.validate(
			"Contact", "links", ["ID", "Bogus"], [["x", "y"]], {0: "name", 1: "no_such_field"}
		)
		self.assertEqual(warnings, [])

	def test_grid_row_reads_dates_and_durations_the_way_the_grid_applies_them(self):
		row = GridImportRow(0, [], "Contact", frappe._dict(columns=[]), import_type=None)
		date_col = frappe._dict(
			df=frappe._dict(fieldtype="Date", label="Date"), column_number=1, date_format="%d-%m-%Y"
		)
		duration_col = frappe._dict(df=frappe._dict(fieldtype="Duration", label="Took"), column_number=2)

		for value in ("25-08-2026", "2026-08-25", "2026-08-25 00:00:00"):
			self.assertEqual(row.get_date(value, date_col), datetime.date(2026, 8, 25))
		self.assertEqual(row.get_date("08/25/2026", date_col), "08/25/2026")

		when = datetime.datetime(2026, 8, 25, 14, 5, 9)
		for value in (format_datetime(when, "dd-MM-yyyy HH:mm:ss"), "2026-08-25 14:05:09"):
			self.assertEqual(row.get_datetime(value, date_col), when)
		self.assertEqual(row.get_datetime("tomorrow", date_col), "tomorrow")

		row.validate_value("3600", duration_col)
		row.validate_value("1h 30m", duration_col)
		self.assertEqual(row.warnings, [])
		row.validate_value("an hour", duration_col)
		self.assertEqual(len(row.warnings), 1)

	def test_google_sheet_url_must_point_at_google_sheets(self):
		for url in (
			"http://docs.google.com/spreadsheets/d/abc/edit",
			"https://example.com/spreadsheets/d/abc/edit",
			"https://docs.google.com/document/d/abc/edit",
		):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				parse_google_sheet("Contact", url)

	def test_permission_is_checked_against_the_parent_doctype(self):
		self.assertRaises(
			frappe.PermissionError,
			lambda: self.with_user("Guest", download_template, "User", "Roles", "[]"),
		)
		self.assertRaises(
			frappe.PermissionError,
			lambda: self.with_user("Guest", parse_file, "User", "roles.csv", as_dataurl(b"role\n")),
		)
		for fn, args in (
			(parse_google_sheet, ("Contact", "https://docs.google.com/spreadsheets/d/abc/edit")),
			(get_column_map, ("Contact", "phone_nos", "[]")),
			(validate_rows, ("Contact", "links", "[]", "[]", "{}")),
		):
			with self.subTest(method=fn.__name__):
				self.assertRaises(frappe.PermissionError, lambda: self.with_user("Guest", fn, *args))

	def with_user(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")
