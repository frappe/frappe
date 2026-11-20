# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.reportview import export_query, extract_fieldnames
from frappe.tests.utils import FrappeTestCase


<<<<<<< HEAD
class TestReportview(FrappeTestCase):
=======
class TestReportview(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		previous_form_dict = frappe.local.form_dict
		self.addCleanup(setattr, frappe.local, "form_dict", previous_form_dict)

	def test_get_field_info_translates_field_labels(self):
		doctype = "Translation"
		translations = {
			"Created On": "Translated Created On",
			"Translated Text": "Translated Field Label",
		}
		for source, translated in translations.items():
			frappe.get_doc(
				{
					"doctype": "Translation",
					"language": "de",
					"source_text": source,
					"translated_text": translated,
					"context": doctype,
				}
			).insert()

		frappe.local.lang = "de"
		try:
			field_info = get_field_info(["creation", "translated_text"], doctype)
		finally:
			frappe.local.lang = "en"

		self.assertEqual(
			[field["label"] for field in field_info],
			["Translated Created On", "Translated Field Label"],
		)

	def test_get_accepts_native_filters_and_fields(self):
		# native dict/list payloads (JSON request body) instead of JSON strings
		frappe.local.form_dict = frappe._dict(
			doctype="ToDo",
			filters={"status": "Open"},
			fields=["name", "status"],
		)
		result = get()
		self.assertIn("keys", result)
		self.assertIn("values", result)

	def test_get_leaves_out_comments_field(self):
		with self.set_user("test@example.com"):
			todo = self.make_todo("Report view comments field")
			todo.add_comment("Comment", "First comment")
			frappe.local.form_dict = frappe._dict(
				doctype="ToDo",
				fields=["name", "_comments", "`tabToDo`.`_comments`"],
				filters={"name": todo.name},
				with_comment_count=1,
			)
			result = get()
			self.assertEqual(result["keys"], ["name", "_comment_count"])
			self.assertEqual(result["values"], [[todo.name, 1]])

			frappe.local.form_dict = frappe._dict(
				doctype="ToDo", fields=["name"], filters=[["ToDo", "_comments", "like", "%a%"]]
			)
			self.assertRaises(frappe.DataError, get)

	def test_get_stats_accepts_native(self):
		# stats as native list (L738) and filters as native list (L740)
		out = get_stats(stats=["_user_tags"], doctype="ToDo", filters=[["ToDo", "status", "=", "Open"]])
		self.assertIsInstance(out, dict)

	def test_get_filter_dashboard_data_accepts_native(self):
		out = get_filter_dashboard_data(
			stats=[{"name": "status", "type": "Select"}], doctype="ToDo", filters=[]
		)
		self.assertIsInstance(out, dict)

	def test_export_query_with_totals_and_translate(self):
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
			add_totals_row=1,
			translate_values=1,
		)
		export_query()
		self.assertTrue(frappe.response["filename"].endswith(".csv"))
		self.assertEqual(frappe.response["type"], "binary")

	def test_append_totals_row_uses_min_and_max_for_min_and_max_aggregates(self):
		fields = [
			"`tabToDo`.`status`",
			{"SUM": "`tabToDo`.`idx`", "as": "_aggregate_column"},
			{"MIN": "`tabToDo`.`idx`", "as": "_aggregate_column_1"},
			"max(`tabToDo`.`idx`) as _aggregate_column_2",
		]
		data = [("Open", 10, 3, 10), ("Closed", 20, 1, 20), ("Cancelled", None, None, None)]

		totals = append_totals_row(data, fields)[-1]

		self.assertEqual(totals, ["Total", 30, 1, 20])

	def test_append_totals_row_sums_without_float_noise(self):
		data = [("Ballpoint Pen", 100.1), ("Notebook", 62.3)]

		totals = append_totals_row(data)[-1]

		self.assertEqual(totals, ["Total", 162.4])

>>>>>>> 1e46e8d (fix(list): leave out _comments instead of failing the list query)
	def test_csv(self):
		from csv import QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC, DictReader
		from io import StringIO

		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
		)

		for delimiter in (",", ";", "\t", "|"):
			frappe.local.form_dict.csv_delimiter = delimiter
			for quoting in (QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC):
				frappe.local.form_dict.csv_quoting = quoting

				export_query()

				self.assertTrue(frappe.response["filename"].endswith(".csv"))
				self.assertEqual(frappe.response["type"], "binary")
				with StringIO(frappe.response["filecontent"].decode("utf-8")) as result:
					reader = DictReader(result, delimiter=delimiter, quoting=quoting)
					for row in reader:
						self.assertEqual(int(row["Is Single"]), 1)
						self.assertEqual(row["Module"], "Core")

	def test_extract_fieldname(self):
		self.assertEqual(
			extract_fieldnames("count(distinct `tabPhoto`.name) as total_count")[0], "tabPhoto.name"
		)

		self.assertEqual(extract_fieldnames("owner")[0], "owner")
		self.assertEqual(extract_fieldnames("from")[0], "from")

		self.assertEqual(extract_fieldnames("module")[0], "module")

		self.assertEqual(extract_fieldnames("count(`tabPhoto`.name) as total_count")[0], "tabPhoto.name")

		self.assertEqual(extract_fieldnames("count(distinct `tabPhoto`.name)")[0], "tabPhoto.name")

		self.assertEqual(extract_fieldnames("count(`tabPhoto`.name)")[0], "tabPhoto.name")

		self.assertEqual(
			extract_fieldnames("count(distinct `tabJob Applicant`.name) as total_count")[0],
			"tabJob Applicant.name",
		)

		self.assertEqual(
			extract_fieldnames("(1 / nullif(locate('a', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name",
		)

		self.assertEqual(
			extract_fieldnames("(1 / nullif(locate('(a)', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name",
		)

		self.assertEqual(extract_fieldnames("EXTRACT(MONTH FROM date_column) AS month")[0], "date_column")

		self.assertEqual(extract_fieldnames("COUNT(*) AS count")[0], "*")

		self.assertEqual(
			extract_fieldnames("first_name + ' ' + last_name AS full_name"), ["first_name", "last_name"]
		)

		self.assertEqual(
			extract_fieldnames("CONCAT(first_name, ' ', last_name) AS full_name"),
			["first_name", "last_name"],
		)

		self.assertEqual(
			extract_fieldnames("CONCAT(id, '/', name, '/', age, '/', marks) AS student"),
			["id", "name", "age", "marks"],
		)

		self.assertEqual(extract_fieldnames("tablefield.fiedname")[0], "tablefield.fiedname")

		self.assertEqual(extract_fieldnames("`tabChild DocType`.`fiedname`")[0], "tabChild DocType.fiedname")

		self.assertEqual(extract_fieldnames("sum(1)"), [])

	def test_export_report_via_email(self):
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
			export_in_background=1,
		)

		frappe.db.delete("Email Queue")
		export_query()
		jobs = frappe.get_all(
			"RQ Job",
			filters={"job_name": "frappe.desk.query_report.run_report_view_export_job"},
			fields=["name", "status"],
		)
		email_queue = frappe.get_all("Email Queue")

		self.assertTrue(jobs, "Background job was not enqueued")
		self.assertTrue(email_queue, "Email was not enqueued")
