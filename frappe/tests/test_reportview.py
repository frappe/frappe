# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.reportview import export_query, extract_fieldnames, get
from frappe.tests.utils import FrappeTestCase


class TestReportview(FrappeTestCase):
	def setUp(self):
		super().setUp()
		previous_form_dict = frappe.local.form_dict
		self.addCleanup(setattr, frappe.local, "form_dict", previous_form_dict)

	def make_todo(self, description):
		return frappe.get_doc(
			doctype="ToDo",
			description=description,
			allocated_to=frappe.session.user,
			assigned_by=frappe.session.user,
		).insert()

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
