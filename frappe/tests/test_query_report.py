# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.utils
from frappe.desk.query_report import build_xlsx_data, export_query, run
from frappe.tests import IntegrationTestCase
from frappe.utils.xlsxutils import make_xlsx


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
		xlsx_data, column_widths = build_xlsx_data(data, visible_idx, include_indentation=0)

		self.assertEqual(type(xlsx_data), list)
		self.assertEqual(len(xlsx_data), 4)  # columns + data
		# column widths are divided by 10 to match the scale that is supported by openpyxl
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
		data.filters = {"Label 1": "Filter Value", "Label 2": None, "Label 3": list(range(5))}

		# Define the visible rows
		visible_idx = [0, 2, 3]

		# Build the result
		xlsx_data, column_widths = build_xlsx_data(
			data, visible_idx, include_indentation=False, include_filters=True
		)

		# Check if unset filters are skipped | Rows - 2 filters + 1 empty + 1 column + 3 data
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
		xlsx_data, column_widths = build_xlsx_data(data, visible_idx, include_indentation=0)
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


def create_mock_data():
	data = frappe._dict()
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
	return data
