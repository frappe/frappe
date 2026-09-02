# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime

import frappe
from frappe.desk.query_report import build_xlsx_data, export_query, format_fields, run
from frappe.tests import IntegrationTestCase
from frappe.utils.xlsxutils import XLSXMetadata, XLSXStyleBuilder, make_xlsx


class TestQueryReport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_save_report_accepts_native_columns_and_filters(self):
		from frappe.desk.query_report import save_report

		frappe.set_user("Administrator")
		ref = frappe.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "ToDo",
				"report_name": "Native Save Reference " + frappe.generate_hash(length=6),
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)

		custom_name = "Native Save Custom " + frappe.generate_hash(length=6)
		frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": custom_name,
				"json": '{"columns":[],"filters":[]}',
				"ref_doctype": "ToDo",
				"is_standard": "No",
				"report_type": "Custom Report",
				"reference_report": ref.name,
			}
		).insert(ignore_permissions=True)

		# columns as a native list and filters as a native dict (frappe.parse_json passthrough)
		docname = save_report(
			ref.name, custom_name, columns=[{"fieldname": "name"}], filters={"status": "Open"}
		)
		saved = json.loads(frappe.get_doc("Report", docname).json)
		self.assertEqual(saved["columns"], [{"fieldname": "name"}])
		self.assertEqual(saved["filters"], {"status": "Open"})

	def test_export_query_coerces_non_list_visible_idx(self):
		frappe.set_user("Administrator")
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "Native Export Query " + frappe.generate_hash(length=6),
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"is_standard": "No",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)

		# visible_idx as a non-list, non-str value is coerced to [] (the new elif branch).
		# The coercion runs before the report executes, so the call must complete without the
		# TypeError that a non-list visible_idx would otherwise cause downstream.
		frappe.local.form_dict = frappe._dict(
			report_name=report.name,
			file_format_type="CSV",
			visible_idx=5,
		)
		frappe.local.response = frappe._dict()
		export_query()
		self.assertIn("type", frappe.local.response)

	def test_export_query_preserves_visible_idx_order(self):
		"""Regression: `export_query` must apply `visible_idx` as an ordered
		list so the UI column-header sort survives into the exported file.

		Old code did ``set(visible_idx)`` and iterated ``data.result`` in its
		default order, discarding the client's sort direction. New code
		iterates ``visible_idx`` so output rows match display order.

		Uses `mock.patch` on `run` so the test is decoupled from actual
		report execution.
		"""
		import csv
		import io
		from unittest.mock import patch

		frappe.set_user("Administrator")

		# Fixed synthetic data — 5 rows in "default order" [A, B, C, D, E].
		# The response the mocked `run` returns for any input.
		fake_data = {
			"result": [
				["row_A", "id_a"],
				["row_B", "id_b"],
				["row_C", "id_c"],
				["row_D", "id_d"],
				["row_E", "id_e"],
			],
			"columns": [
				{"label": "Description", "fieldname": "description", "fieldtype": "Data"},
				{"label": "ID", "fieldname": "name", "fieldtype": "Data"},
			],
			"add_total_row": 0,
			"applied_filters": {},
			"filters": {},
		}

		# Minimal report to satisfy get_report_doc(); export_query looks up
		# report_name to check permissions. The report's own body is unused
		# because `run` is mocked.
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": f"Sort Order Export {frappe.generate_hash(length=6)}",
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"is_standard": "No",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)

		# Non-identity, non-reverse permutation to catch order bugs. If the
		# server iterated data.result (old code), the output would be A/B/C/D/E.
		# If it iterates visible_idx (fixed code), output is D/A/E/B/C.
		reorder = [3, 0, 4, 1, 2]
		expected_descriptions = [fake_data["result"][i][0] for i in reorder]

		frappe.local.form_dict = frappe._dict(
			report_name=report.name,
			file_format_type="CSV",
			visible_idx=reorder,
			applied_filters={},
			filters={},
		)
		frappe.local.response = frappe._dict()

		with patch("frappe.desk.query_report.run", return_value=fake_data):
			export_query()

		self.assertIn(
			"filecontent",
			frappe.local.response,
			f"export_query didn't produce a file, got: {dict(frappe.local.response)!r}",
		)
		csv_bytes = frappe.local.response["filecontent"]
		if isinstance(csv_bytes, bytes):
			csv_bytes = csv_bytes.decode("utf-8")

		# Data rows carry our "row_" marker; header row does not.
		all_rows = list(csv.reader(io.StringIO(csv_bytes)))
		data_rows = [r for r in all_rows if r and r[0].startswith("row_")]
		self.assertEqual(
			len(data_rows),
			5,
			f"expected 5 data rows in CSV, got {len(data_rows)}: {data_rows!r}",
		)

		actual_descriptions = [r[0] for r in data_rows]
		self.assertEqual(
			actual_descriptions,
			expected_descriptions,
			"CSV row order should follow visible_idx sequence, not default order",
		)

	def test_xlsx_data_with_multiple_datatypes(self):
		"""Test exporting report using rows with multiple datatypes (list, dict)"""

		# Create mock data
		data = create_mock_data()

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data, column_widths, _ = build_xlsx_data(data, visible_idx, include_indentation=0)

		self.assertEqual(type(xlsx_data), list)
		self.assertEqual(len(xlsx_data), 4)  # columns + data
		# column widths are divided by 10 to match the scale that is supported by xlsxwriter
		self.assertListEqual(column_widths, [0, 10, 15])

		for row in xlsx_data:
			self.assertIsInstance(row, list)

		# ensure all types are preserved
		for row in xlsx_data[1:]:
			for cell in row:
				self.assertIsInstance(cell, (int, float))

	def test_xlsx_data_with_filters(self):
		"""Test building xlsx data along with filters"""

		# Create mock data
		data = create_mock_data()

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data, _column_widths, _ = build_xlsx_data(
			data,
			visible_idx,
			include_indentation=False,
			include_filters=True,
		)

		# Check if unset filters are skipped | Rows -> 2 filters + 1 empty + 1 column + 3 data
		self.assertEqual(len(xlsx_data), 7)

		# Check filter formatting
		self.assertListEqual(xlsx_data[:2], [["Label 1", "Filter Value"], ["Label 3", "0, 1, 2, 3, 4"]])

	def test_xlsx_export_with_composite_cell_value(self):
		"""Test excel export using rows with composite cell value"""

		data = frappe._dict()

		data.columns = [
			{"label": "Column A", "fieldname": "column_a", "fieldtype": "Float"},
			{"label": "Column B", "fieldname": "column_b", "width": 150, "fieldtype": "Data"},
		]
		data.result = [
			[1.0, "Dummy 1"],
			{"column_a": 22.1, "column_b": ["Dummy 1", "Dummy 2"]},  # composite value in column_b
		]

		# Define the visible rows
		visible_idx = [0, 1]

		# Build the result
		xlsx_data, column_widths, _ = build_xlsx_data(data, visible_idx, include_indentation=0)
		# Export to excel
		make_xlsx(xlsx_data, "Query Report", column_widths=column_widths)

		for row in xlsx_data:
			# column_b should be 'str' even with composite cell value
			self.assertEqual(type(row[1]), str)

	def test_xlsx_export_preserves_date_objects(self):
		"""Date/Datetime columns must reach Excel as real date objects, while CSV keeps strings"""

		posting_date = datetime.date(2026, 6, 1)
		created_on = datetime.datetime(2026, 6, 1, 9, 30)

		def make_data():
			return frappe._dict(
				report_name="",
				columns=[
					{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date"},
					{"label": "Created On", "fieldname": "created_on", "fieldtype": "Datetime"},
				],
				result=[{"posting_date": posting_date, "created_on": created_on}],
				filters={},
				applied_filters={},
			)

		# Excel: date objects are preserved so make_xlsx can write real date cells
		excel_data = make_data()
		format_fields(excel_data, "Excel")
		self.assertEqual(excel_data.result[0]["posting_date"], posting_date)
		self.assertIsInstance(excel_data.result[0]["created_on"], datetime.datetime)

		# build_xlsx_data passes the date through untouched for the Excel sheet
		xlsx_data, _, styles = build_xlsx_data(excel_data, build_styles=True)
		self.assertIsInstance(xlsx_data[1][0], datetime.date)
		self.assertIsInstance(xlsx_data[1][1], datetime.datetime)

		# the Date column carries a date number_format so Excel renders it as a date
		date_style = {}
		col0_style_ids = styles["column_styles"].get(0)
		self.assertIsNotNone(col0_style_ids, "No column style registered for the Date column")
		for sid in col0_style_ids:
			date_style.update(styles["styles"][sid])
		self.assertIn("num_format", date_style)

		# CSV (default): dates are stringified for display
		csv_data = make_data()
		format_fields(csv_data)
		self.assertIsInstance(csv_data.result[0]["posting_date"], str)
		self.assertIsInstance(csv_data.result[0]["created_on"], str)

	def test_csv(self):
		from csv import QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC, DictReader
		from io import StringIO

		REPORT_NAME = "Test CSV Report"
		REF_DOCTYPE = "DocType"
		REPORT_COLUMNS = ["name", "module", "issingle"]

		if not frappe.db.exists("Report", REPORT_NAME):
			report = frappe.new_doc("Report")
			report.report_name = REPORT_NAME
			report.ref_doctype = "User"
			report.report_type = "Query Report"
			report.query = frappe.qb.from_(REF_DOCTYPE).select(*REPORT_COLUMNS).limit(10).get_sql()
			report.is_standard = "No"
			report.save()

		for delimiter in (",", ";", "\t", "|"):
			for quoting in (QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC):
				frappe.local.form_dict = frappe._dict(
					{
						"report_name": REPORT_NAME,
						"file_format_type": "CSV",
						"csv_quoting": quoting,
						"csv_delimiter": delimiter,
						"include_indentation": 0,
						"visible_idx": [0, 1, 2],
					}
				)
				export_query()

				self.assertTrue(frappe.response["filename"].endswith(".csv"))
				self.assertEqual(frappe.response["type"], "binary")
				with StringIO(frappe.response["filecontent"].decode("utf-8")) as result:
					reader = DictReader(result, delimiter=delimiter, quoting=quoting)
					row = reader.__next__()
					for column in REPORT_COLUMNS:
						self.assertIn(column, row)

		frappe.delete_doc("Report", REPORT_NAME, delete_permanently=True)

	def test_report_for_duplicate_column_names(self):
		"""Test report with duplicate column names"""

		try:
			fields = [
				{"label": "First Name", "fieldname": "first_name", "fieldtype": "Data"},
				{"label": "Last Name", "fieldname": "last_name", "fieldtype": "Data"},
			]
			frappe.get_doc(
				{
					"doctype": "DocType",
					"name": "Doc A",
					"module": "Core",
					"custom": 1,
					"autoname": "field:first_name",
					"fields": fields,
					"permissions": [{"role": "System Manager"}],
				}
			).insert(ignore_if_duplicate=True)

			frappe.get_doc(
				{
					"doctype": "DocType",
					"name": "Doc B",
					"module": "Core",
					"custom": 1,
					"autoname": "field:last_name",
					"fields": fields,
					"permissions": [{"role": "System Manager"}],
				}
			).insert(ignore_if_duplicate=True)

			for i in range(1, 3):
				frappe.get_doc({"doctype": "Doc A", "first_name": f"John{i}", "last_name": "Doe"}).insert()
				frappe.get_doc({"doctype": "Doc B", "last_name": f"Doe{i}", "first_name": "John"}).insert()

			if not frappe.db.exists("Report", "Doc A Report"):
				report = frappe.get_doc(
					{
						"doctype": "Report",
						"ref_doctype": "Doc A",
						"report_name": "Doc A Report",
						"report_type": "Script Report",
						"is_standard": "No",
					}
				).insert(ignore_permissions=True)
			else:
				report = frappe.get_doc("Report", "Doc A Report")

			report.report_script = """
result = [["Ritvik","Sardana", "Doe1"],["Shariq","Ansari", "Doe2"]]
columns = [{
			"label": "First Name",
			"fieldname": "first_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Last Name",
			"fieldname": "last_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Linked Field",
			"fieldname": "linked_field",
			"fieldtype": "Link",
			"options": "Doc B",
			"width": 180,
		},
	]

data = columns, result
				"""
			report.save()

			custom_columns = [
				{
					"fieldname": "first_name-Doc_B",
					"fieldtype": "Data",
					"label": "First Name",
					"insert_after_index": 1,
					"link_field": {"fieldname": "linked_field", "names": {}},
					"doctype": "Doc B",
					"width": 100,
					"id": "first_name-Doc_B",
					"name": "First Name",
					"editable": False,
					"compareValue": None,
				},
			]

			response = run(
				"Doc A Report",
				filters={"user": "Administrator", "doctype": "Doc A"},
				custom_columns=custom_columns,
			)

			self.assertListEqual(
				["first_name", "last_name", "first_name-Doc_B", "linked_field"],
				[d["fieldname"] for d in response["columns"]],
			)

			self.assertDictEqual(
				{
					"first_name": "Ritvik",
					"last_name": "Sardana",
					"linked_field": "Doe1",
					"first_name-Doc_B": "John",
				},
				response["result"][0],
			)

		except Exception as e:
			raise e
			frappe.db.rollback()

	def test_xlsx_styles_structure(self):
		"""build_xlsx_data with build_styles=True returns a well-formed styles dict"""
		data = create_mock_data()
		data.pop("report_name")  # module not needed for this test

		_, _, styles = build_xlsx_data(data, build_styles=True)

		self.assertIsNotNone(styles)
		for key in ("styles", "column_styles", "row_styles", "cell_styles"):
			self.assertIn(key, styles)

		# style registry must be non-empty
		self.assertGreater(len(styles["styles"]), 0)

		# header row (index 0, no filters included) must have bold style
		self.assertIn(0, styles["row_styles"])

		# resolve the header row's style IDs and confirm bold is set
		registry = styles["styles"]
		header_style_ids = styles["row_styles"][0]
		header_merged = {}
		for sid in header_style_ids:
			header_merged.update(registry[sid])
		self.assertTrue(header_merged.get("bold"))

	def test_xlsx_style_builder_fieldtype_column_styles(self):
		"""XLSXStyleBuilder applies column styles for Float/Percent/Date but not Data"""
		column_map = {
			0: {"fieldname": "name", "fieldtype": "Data", "label": "Name"},
			1: {"fieldname": "score", "fieldtype": "Float", "label": "Score"},
			2: {"fieldname": "pct", "fieldtype": "Percent", "label": "Pct"},
			3: {"fieldname": "dt", "fieldtype": "Date", "label": "Date"},
		}
		row_map = {1: {"name": "A", "score": 1.0, "pct": 10.0, "dt": "2025-01-01"}}

		metadata = XLSXMetadata(column_map=column_map, row_map=row_map)
		builder = XLSXStyleBuilder(metadata, default_styling=False)
		builder.apply_default_fieldtype_formats(currency_formatting=False)

		def resolve(col_idx):
			"""Merge all style dicts registered for a column into one dict."""
			merged = {}
			for sid in builder.column_styles[col_idx]:
				merged.update(builder.styles[sid])
			return merged

		# Float, Percent, Date → column-level styles
		self.assertIn(1, builder.column_styles)
		self.assertIn(2, builder.column_styles)
		self.assertIn(3, builder.column_styles)

		# Data column → no column style
		self.assertNotIn(0, builder.column_styles)

		# Float → has num_format, no alignment override
		float_style = resolve(1)
		self.assertIn("num_format", float_style)
		self.assertNotIn("align", float_style)

		# Percent → num_format contains "%"
		percent_style = resolve(2)
		self.assertIn("num_format", percent_style)
		self.assertIn("%", percent_style["num_format"])

		# Date → has num_format and explicitly right-aligned
		date_style = resolve(3)
		self.assertIn("num_format", date_style)
		self.assertEqual(date_style.get("align"), "right")

	def test_export_report_via_email(self):
		REPORT_NAME = "Test CSV Report"
		REF_DOCTYPE = "DocType"
		REPORT_COLUMNS = ["name", "module", "issingle"]

		if not frappe.db.exists("Report", REPORT_NAME):
			report = frappe.new_doc("Report")
			report.report_name = REPORT_NAME
			report.ref_doctype = "User"
			report.report_type = "Query Report"
			report.query = frappe.qb.from_(REF_DOCTYPE).select(*REPORT_COLUMNS).limit(10).get_sql()
			report.is_standard = "No"
			report.save()

		frappe.local.form_dict = frappe._dict(
			{
				"report_name": REPORT_NAME,
				"file_format_type": "CSV",
				"include_indentation": 0,
				"visible_idx": [0, 1, 2],
				"export_in_background": 1,
			}
		)
		frappe.db.delete("Email Queue")
		export_query()

		jobs = frappe.get_all("RQ Job")
		email_queue = frappe.get_all("Email Queue")

		self.assertTrue(jobs, "Background job was not enqueued")
		self.assertTrue(email_queue, "Email was not enqueued")

		frappe.delete_doc("Report", REPORT_NAME, delete_permanently=True)


def create_mock_data():
	data = frappe._dict()
	data.report_name = "Mock Report"

	data.columns = [
		{"label": "Column A", "fieldname": "column_a", "fieldtype": "Float"},
		{"label": "Column B", "fieldname": "column_b", "width": 100, "fieldtype": "Float"},
		{"label": "Column C", "fieldname": "column_c", "width": 150, "fieldtype": "Duration"},
	]

	data.result = [
		[1.0, 3.0, 600],
		{"column_a": 22.1, "column_b": 21.8, "column_c": 86412},
		{"column_b": 5.1, "column_c": 53234, "column_a": 11.1},
		[3.0, 1.5, 333],
	]

	data.applied_filters = {"Label 1": "Filter Value", "Label 2": None, "Label 3": list(range(5))}
	data.filters = {"label_1": "Filter Value", "label_2": None, "label_3": list(range(5))}

	return data
