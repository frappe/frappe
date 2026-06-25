# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.reportview import export_query, extract_fieldnames, get_columns_with_data
from frappe.tests import IntegrationTestCase


class TestReportview(IntegrationTestCase):
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


class TestColumnsWithData(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.child_doctype = (
			new_doctype(
				istable=1,
				fields=[{"fieldname": "child_text", "fieldtype": "Data", "label": "Child Text"}],
			)
			.insert(ignore_permissions=True)
			.name
		)
		cls.doctype = (
			new_doctype(
				fields=[
					{"fieldname": "text_field", "fieldtype": "Data", "label": "Text Field"},
					{"fieldname": "amount", "fieldtype": "Int", "label": "Amount"},
					{"fieldname": "flag", "fieldtype": "Check", "label": "Flag"},
					{"fieldname": "happened_on", "fieldtype": "Date", "label": "Happened On"},
					{
						"fieldname": "rows",
						"fieldtype": "Table",
						"label": "Rows",
						"options": cls.child_doctype,
					},
					{"fieldname": "secret", "fieldtype": "Data", "label": "Secret", "permlevel": 1},
				],
			)
			.insert(ignore_permissions=True)
			.name
		)
		# The parent references the child table, so it must be dropped first; cleanups run LIFO.
		cls.addClassCleanup(frappe.delete_doc, "DocType", cls.child_doctype, force=True)
		cls.addClassCleanup(frappe.delete_doc, "DocType", cls.doctype, force=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _make(self, **values):
		return frappe.get_doc(doctype=self.doctype, **values).insert(ignore_permissions=True)

	def _columns(self, name):
		return get_columns_with_data(self.doctype, [[self.doctype, "name", "=", name]])

	def test_only_fields_with_data_returned(self):
		doc = self._make(text_field="hello", amount=5, flag=1)
		fields = self._columns(doc.name)[self.doctype]
		self.assertIn("text_field", fields)
		self.assertIn("amount", fields)
		self.assertIn("flag", fields)  # a ticked checkbox counts as data
		self.assertNotIn("happened_on", fields)  # left NULL

	def test_standard_columns_included(self):
		doc = self._make(text_field="hello")
		fields = self._columns(doc.name)[self.doctype]
		# Always-populated standard columns are reported too, so the result is exactly the
		# columns that hold data (not just the doctype's own fields).
		for standard_field in ("name", "owner", "creation", "modified", "modified_by"):
			self.assertIn(standard_field, fields)

	def test_empty_values_excluded(self):
		doc = self._make(text_field="", amount=0, flag=0)
		fields = self._columns(doc.name).get(self.doctype, [])
		self.assertNotIn("text_field", fields)  # empty string
		self.assertNotIn("amount", fields)  # zero
		self.assertNotIn("flag", fields)  # unticked checkbox
		self.assertNotIn("happened_on", fields)  # NULL date

	def test_scoped_to_matching_records(self):
		with_data = self._make(text_field="present")
		without = self._make(text_field="")

		# Only the empty record matches the filter -> the column reads as empty.
		self.assertNotIn("text_field", self._columns(without.name).get(self.doctype, []))
		# The populated record matches -> the column reads as having data.
		self.assertIn("text_field", self._columns(with_data.name)[self.doctype])

	def test_child_table_fields(self):
		doc = self._make(text_field="parent")
		doc.append("rows", {"child_text": "child value"})
		doc.save(ignore_permissions=True)

		columns = self._columns(doc.name)
		self.assertIn(self.child_doctype, columns)
		self.assertIn("child_text", columns[self.child_doctype])

	def test_child_table_absent_when_empty(self):
		doc = self._make(text_field="parent only")
		self.assertNotIn(self.child_doctype, self._columns(doc.name))

	def test_no_matching_records(self):
		self._make(text_field="present")
		# A filter that matches nothing should report no columns at all.
		self.assertEqual(get_columns_with_data(self.doctype, [[self.doctype, "name", "=", "missing"]]), {})

	def test_skips_fields_without_permlevel_access(self):
		# `secret` is permlevel 1 and the doctype grants no permlevel-1 access, so a
		# non-admin user must not see it reported even though it holds data.
		doc = self._make(text_field="visible", secret="classified")

		restricted = "cwd-restricted@example.com"
		if not frappe.db.exists("User", restricted):
			frappe.get_doc(
				doctype="User",
				email=restricted,
				first_name="CWD",
				roles=[{"role": "System Manager"}],
			).insert(ignore_permissions=True)

		frappe.set_user(restricted)
		try:
			fields = self._columns(doc.name)[self.doctype]
		finally:
			frappe.set_user("Administrator")

		self.assertIn("text_field", fields)
		self.assertNotIn("secret", fields)
