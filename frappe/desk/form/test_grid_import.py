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

USER = "test2@example.com"
HEADER = ["ID", "Number (phone)"]


def as_dataurl(content: bytes) -> str:
	return "data:application/octet-stream;base64," + base64.b64encode(content).decode()


class TestGridImport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.other_contact = frappe.get_doc({"doctype": "Contact", "first_name": "Not Yours"}).insert().name
		frappe.set_user(USER)
		cls.contact = frappe.get_doc({"doctype": "Contact", "first_name": "Grid Import"}).insert().name
		frappe.set_user("Administrator")

	def setUp(self):
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_download_returns_an_xlsx_binary(self):
		rows = [HEADER, ["", "+91-9876543210"]]
		download_template("Contact", "Numbers", json.dumps(rows), docname=self.contact)

		self.assertEqual(frappe.response["type"], "binary")
		self.assertEqual(frappe.response["filename"], "Numbers.xlsx")
		self.assertTrue(frappe.response["filecontent"].startswith(b"PK"))

	def test_download_csv_keeps_phone_numbers_as_text(self):
		rows = [["Number"], ["+91-9876543210"]]
		download_template("Contact", "Numbers", json.dumps(rows), "CSV", docname=self.contact)

		self.assertEqual(frappe.response["type"], "csv")
		self.assertIn("'+91-9876543210", frappe.response["result"])

	def test_download_rejects_unsupported_file_type(self):
		with self.assertRaises(frappe.ValidationError):
			download_template("Contact", "Numbers", json.dumps([HEADER]), "PDF", docname=self.contact)

	def test_download_allows_the_full_row_limit(self):
		rows = [["Number"], *([["1"]] * MAX_TEMPLATE_ROWS)]
		download_template("Contact", "Numbers", json.dumps(rows), docname=self.contact)
		self.assertEqual(frappe.response["type"], "binary")

	def test_download_rejects_oversized_template(self):
		rows = [["Number"], *([["1"]] * (MAX_TEMPLATE_ROWS + 1))]
		with self.assertRaises(frappe.ValidationError):
			download_template("Contact", "Numbers", json.dumps(rows), docname=self.contact)

	def parse(self, filename, content):
		return parse_file("Contact", filename, as_dataurl(content), docname=self.contact)

	def test_xlsx_and_csv_uploads_agree(self):
		rows = [HEADER, ["", "+91-9876543210"]]

		xlsx = self.parse("numbers.xlsx", make_xlsx(rows, "Numbers").getvalue())
		csv = self.parse("numbers.csv", "\n".join(",".join(f'"{c}"' for c in row) for row in rows).encode())

		self.assertEqual(xlsx, rows)
		self.assertEqual(csv, rows)

	def test_template_header_maps_back_to_its_fields(self):
		column_map = get_column_map("Contact", "phone_nos", json.dumps(HEADER), docname=self.contact)
		self.assertEqual(column_map, {0: "name", 1: "phone"})

	def test_upload_rejects_unsupported_extension(self):
		with self.assertRaises(frappe.ValidationError):
			self.parse("numbers.txt", b"phone\n")

	def test_upload_rejects_empty_content(self):
		with self.assertRaises(frappe.ValidationError):
			parse_file("Contact", "numbers.csv", "", docname=self.contact)

	def test_dates_round_trip_through_a_spreadsheet(self):
		rows = [HEADER, [datetime.date(2026, 8, 25), "+91-9876543210"]]
		parsed = self.parse("numbers.xlsx", make_xlsx(rows, "Numbers").getvalue())
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
		parsed = self.parse("times.xlsx", make_xlsx(rows, "Times").getvalue())
		self.assertEqual(parsed[1][0], "2026-08-25 14:05:09")
		self.assertEqual(parsed[2][0], "09:30:00")

	def test_column_map_matches_label_fieldname_and_template_header(self):
		headers = ["Number (phone)", "Is Primary Phone", "is_primary_mobile_no", "ID", "Nonsense", ""]
		column_map = get_column_map("Contact", "phone_nos", json.dumps(headers), docname=self.contact)

		self.assertEqual(
			column_map,
			{0: "phone", 1: "is_primary_phone", 2: "is_primary_mobile_no", 3: "name"},
		)

	def test_column_map_includes_read_only_fields(self):
		headers = ["Link Document Type (link_doctype)", "Link Title (link_title)"]
		column_map = get_column_map("Contact", "links", json.dumps(headers), docname=self.contact)

		self.assertEqual(column_map, {0: "link_doctype", 1: "link_title"})

	def test_column_map_rejects_a_non_table_field(self):
		with self.assertRaises(frappe.ValidationError):
			get_column_map("Contact", "first_name", json.dumps(["Number (phone)"]), docname=self.contact)

	def validate(self, doctype, fieldname, headers, rows, column_map, docname=None):
		return validate_rows(
			doctype,
			fieldname,
			json.dumps(headers),
			json.dumps(rows),
			json.dumps(column_map),
			docname=docname,
		)

	def test_validate_rows_flags_missing_link_records(self):
		rows = [["User"], ["No Such DocType"], [""]]
		warnings = self.validate(
			"Contact", "links", ["Link Document Type"], rows, {0: "link_doctype"}, self.contact
		)

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
		rows = [["Yes"], ["Someday"]]
		warnings = self.validate("Event", "event_participants", ["Attending"], rows, {0: "attending"})

		self.assertEqual([(w["row"], w["col"]) for w in warnings], [(1, 0)])
		self.assertTrue(warnings[0]["message"].startswith('"Someday" is not valid. Allowed: Yes'))

	def test_validate_rows_checks_link_values_with_one_query_per_column(self):
		rows = [["User"], ["No Such DocType"]] * 25

		with patch("frappe.get_all", wraps=frappe.get_all) as get_all:
			warnings = self.validate(
				"Contact", "links", ["Link Document Type"], rows, {0: "link_doctype"}, self.contact
			)

		doctype_queries = [c for c in get_all.call_args_list if c.args[:1] == ("DocType",)]
		self.assertEqual(len(doctype_queries), 1)
		self.assertEqual(len(warnings), 25)

	def test_validate_rows_rejects_more_rows_than_an_import_allows(self):
		rows = [["1"]] * MAX_IMPORT_ROWS
		self.assertEqual(self.validate("Contact", "phone_nos", ["Number"], rows, {}, self.contact), [])
		with self.assertRaises(frappe.ValidationError):
			self.validate("Contact", "phone_nos", ["Number"], [*rows, ["1"]], {}, self.contact)

	def test_validate_rows_reports_rows_of_the_wrong_width(self):
		warnings = self.validate(
			"Contact", "phone_nos", ["Number", "Primary"], [["123"]], {0: "phone"}, self.contact
		)

		self.assertEqual(len(warnings), 1)
		self.assertEqual(warnings[0]["row"], 0)
		self.assertIsNone(warnings[0]["col"])
		self.assertFalse(warnings[0]["blocking"])

	def test_validate_rows_ignores_fields_that_cannot_be_imported(self):
		warnings = self.validate(
			"Contact", "links", ["ID", "Bogus"], [["x", "y"]], {0: "name", 1: "no_such_field"}, self.contact
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

	def test_grid_row_checks_phone_fields_the_way_a_save_does(self):
		row = GridImportRow(0, [], "Contact", frappe._dict(columns=[]), import_type=None)
		phone_col = frappe._dict(df=frappe._dict(fieldtype="Phone", label="Mobile"), column_number=1)
		frappe.clear_messages()

		self.assertEqual(row.validate_value("+91-9876543210", phone_col), "+91-9876543210")
		self.assertEqual(row.warnings, [])

		for value in ("9876543210", "+91-123", "call-me"):
			self.assertIsNone(row.validate_value(value, phone_col))
		self.assertEqual(len(row.warnings), 3)
		self.assertEqual(
			row.warnings[0]["message"], '"9876543210" needs a country code, like +91-9876543210.'
		)
		self.assertNotIn("country code", row.warnings[1]["message"])
		self.assertEqual(frappe.get_message_log(), [])

	def test_google_sheet_url_must_point_at_google_sheets(self):
		for url in (
			"http://docs.google.com/spreadsheets/d/abc/edit",
			"https://example.com/spreadsheets/d/abc/edit",
			"https://docs.google.com/document/d/abc/edit",
		):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				parse_google_sheet("Contact", url, docname=self.contact)

	def test_owner_can_import_into_their_own_document_only(self):
		headers = json.dumps(["Number (phone)"])
		self.assertEqual(get_column_map("Contact", "phone_nos", headers, docname=self.contact), {0: "phone"})

		for docname in (self.other_contact, None):
			with self.subTest(docname=docname), self.assertRaises(frappe.PermissionError):
				get_column_map("Contact", "phone_nos", headers, docname=docname)

	def test_permission_is_checked_against_the_parent_doctype(self):
		for fn, args in (
			(download_template, ("Contact", "Numbers", "[]")),
			(parse_file, ("Contact", "numbers.csv", as_dataurl(b"phone\n"))),
			(parse_google_sheet, ("Contact", "https://docs.google.com/spreadsheets/d/abc/edit")),
			(get_column_map, ("Contact", "phone_nos", "[]")),
			(validate_rows, ("Contact", "links", "[]", "[]", "{}")),
		):
			with self.subTest(method=fn.__name__):
				frappe.set_user("Guest")
				self.assertRaises(frappe.PermissionError, fn, *args, docname=self.contact)
