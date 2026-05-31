# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from typing import ClassVar

import frappe
from frappe.desk.query_report import build_xlsx_data, export_query, run
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import build_report_pdf_html, download_report_pdf
from frappe.utils.xlsxutils import XLSXMetadata, XLSXStyleBuilder, make_xlsx


class TestQueryReport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enterClassContext(cls.enable_safe_exec())
		return super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

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
				frappe.db.commit()
				export_query()

				self.assertTrue(frappe.response["filename"].endswith(".csv"))
				self.assertEqual(frappe.response["type"], "binary")
				with StringIO(frappe.response["filecontent"].decode("utf-8")) as result:
					reader = DictReader(result, delimiter=delimiter, quoting=quoting)
					row = reader.__next__()
					for column in REPORT_COLUMNS:
						self.assertIn(column, row)

		frappe.delete_doc("Report", REPORT_NAME, delete_permanently=True)
		frappe.db.commit()

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
		frappe.db.commit()
		export_query()

		email_queue = frappe.get_all("Email Queue")

		self.assertTrue(email_queue, "Email was not enqueued")

		frappe.delete_doc("Report", REPORT_NAME, delete_permanently=True)
		frappe.db.commit()


class TestDownloadReportPDF(IntegrationTestCase):
	REPORT_NAME = "Test PDF Report"
	ESCAPE_REPORT_NAME = "Test PDF Escape Report"
	TOTAL_REPORT_NAME = "Test PDF Total Report"
	RICH_REPORT_NAME = "Test PDF Rich Report"
	CHECK_REPORT_NAME = "Test PDF Check Report"
	EDITOR_REPORT_NAME = "Test PDF Editor Report"

	# report_name -> extra fields merged into the default Query Report definition
	REPORTS: ClassVar[dict] = {
		REPORT_NAME: {"query": "SELECT name, module, issingle FROM tabDocType LIMIT 10"},
		ESCAPE_REPORT_NAME: {"query": "SELECT '<b>x</b>' AS label"},
		TOTAL_REPORT_NAME: {
			"add_total_row": 1,
			"query": "SELECT 'A' AS item, 10 AS amount UNION SELECT 'B', 20",
		},
		# Code/Text columns (via the "Label:Fieldtype" hint) must be escaped, not trusted
		RICH_REPORT_NAME: {
			"query": (
				"SELECT '<b>x</b>' AS \"Snippet:Code:200\", "
				"CONCAT('a<i>y</i>', CHAR(10), 'z') AS \"Note:Text:200\""
			),
		},
		CHECK_REPORT_NAME: {"query": 'SELECT 1 AS "Active:Check:80" UNION SELECT 0'},
		# Text Editor holds backend-sanitized HTML and must render as-is
		EDITOR_REPORT_NAME: {"query": "SELECT '<b>x</b>' AS \"Body:Text Editor:200\""},
	}

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		for report_name, overrides in cls.REPORTS.items():
			if not frappe.db.exists("Report", report_name):
				frappe.get_doc(
					{
						"doctype": "Report",
						"report_name": report_name,
						"ref_doctype": "DocType",
						"report_type": "Query Report",
						"is_standard": "No",
						"letter_head": "",
						**overrides,
					}
				).insert(ignore_permissions=True)
		# reports must be committed: run() opens a read-only transaction that both needs
		# to see them and refuses to start while uncommitted writes are pending
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls) -> None:
		for report_name in cls.REPORTS:
			frappe.delete_doc("Report", report_name, delete_permanently=True)
		# persist the fixture cleanup above
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self) -> None:
		# download_report_pdf writes an access log (direct insert in test mode); drop it so
		# the next test's read-only report run does not trip ImplicitCommitError
		frappe.db.rollback()
		super().tearDown()

	def test_basic_pdf_generation(self):
		download_report_pdf(report_name=self.REPORT_NAME)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)
		self.assertIn(self.REPORT_NAME.replace(" ", "-"), frappe.local.response.filename)

	def test_selected_columns(self):
		download_report_pdf(
			report_name=self.REPORT_NAME,
			print_settings=json.dumps({"columns": ["name", "module"]}),
		)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)

	def test_selected_non_prefix_columns_keep_alignment(self):
		"""Dropping a middle column must not leak its values under a kept later column."""
		html, _ = build_report_pdf_html(
			self.REPORT_NAME,
			print_settings={"columns": ["name", "issingle"]},
		)

		self.assertIn("issingle", html)
		self.assertNotIn(">Module<", html)
		self.assertNotIn("Core", html)

	def test_orientation_portrait(self):
		download_report_pdf(report_name=self.REPORT_NAME, orientation="Portrait")

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)

	def test_with_letterhead(self):
		letterhead_name = frappe.db.get_value("Letter Head", {"is_default": 1})
		if not letterhead_name:
			self.skipTest("No default Letter Head configured")

		download_report_pdf(
			report_name=self.REPORT_NAME,
			print_settings=json.dumps(
				{
					"with_letter_head": 1,
					"letter_head_name": letterhead_name,
				}
			),
		)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)

	def test_with_filters_in_filename(self):
		download_report_pdf(
			report_name=self.REPORT_NAME,
			filters=json.dumps({"module": "Core"}),
		)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertIn("Core", frappe.local.response.filename)

	def test_permission_denied_for_guest(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, download_report_pdf, report_name=self.REPORT_NAME)
		finally:
			frappe.set_user("Administrator")

	def test_list_rows_converted_to_dict(self):
		result = run(self.REPORT_NAME)
		fieldnames = [c["fieldname"] for c in result["columns"]]
		row = result["result"][0]
		values = row if isinstance(row, list) else [row[f] for f in fieldnames]
		name, module = values[0], values[1]

		html, _ = build_report_pdf_html(self.REPORT_NAME)

		self.assertIn(name, html)
		self.assertIn(module, html)

	def test_check_field_formatting(self):
		download_report_pdf(report_name=self.REPORT_NAME)

		content = frappe.local.response.filecontent
		self.assertIsInstance(content, bytes)
		self.assertTrue(len(content) > 0)

	def test_are_default_filters_false(self):
		download_report_pdf(
			report_name=self.REPORT_NAME,
			filters=json.dumps({}),
			are_default_filters=False,
		)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)

	def test_js_filters_passed(self):
		js_filters = [{"fieldname": "module", "fieldtype": "Link", "options": "Module Def"}]
		download_report_pdf(
			report_name=self.REPORT_NAME,
			filters=json.dumps({"module": "Core"}),
			js_filters=json.dumps(js_filters),
		)

		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertTrue(frappe.local.response.filecontent)

	def test_html_in_cell_values_is_escaped(self):
		html, _ = build_report_pdf_html(self.ESCAPE_REPORT_NAME)

		self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
		self.assertNotIn("<b>x</b>", html)

	def test_code_field_value_is_escaped_in_pre(self):
		html, _ = build_report_pdf_html(self.RICH_REPORT_NAME)

		self.assertIn("<pre>&lt;b&gt;x&lt;/b&gt;</pre>", html)
		self.assertNotIn("<b>x</b>", html)

	def test_text_field_value_is_escaped_with_newlines(self):
		html, _ = build_report_pdf_html(self.RICH_REPORT_NAME)

		self.assertIn("a&lt;i&gt;y&lt;/i&gt;<br>z", html)
		self.assertNotIn("<i>y</i>", html)

	def test_check_field_rendering(self):
		html, _ = build_report_pdf_html(self.CHECK_REPORT_NAME)

		self.assertIn("✓", html)
		self.assertIn("✗", html)

	def test_text_editor_value_rendered_raw(self):
		# Text Editor holds backend-sanitized HTML and is rendered without escaping
		html, _ = build_report_pdf_html(self.EDITOR_REPORT_NAME)

		self.assertIn("<b>x</b>", html)

	def test_filters_rendered_and_escaped(self):
		html, _ = build_report_pdf_html(
			self.REPORT_NAME,
			filters={"module": "<b>Core</b>"},
			print_settings={"include_filters": 1},
		)

		self.assertIn("&lt;b&gt;Core&lt;/b&gt;", html)
		self.assertNotIn("<b>Core</b>", html)

	def test_total_row_is_bold(self):
		self.assertTrue(run(self.TOTAL_REPORT_NAME).get("add_total_row"))

		html, _ = build_report_pdf_html(self.TOTAL_REPORT_NAME)

		self.assertIn("font-weight: bold", html)
		self.assertIn("30", html)


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
