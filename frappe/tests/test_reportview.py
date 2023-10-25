# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.reportview import export_query, extract_fieldname
from frappe.tests.utils import FrappeTestCase


class TestReportview(FrappeTestCase):
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
			extract_fieldname("count(distinct `tabPhoto`.name) as total_count")[0],
			"tabPhoto.name"
		)

		self.assertEqual(
			extract_fieldname("count(`tabPhoto`.name) as total_count")[0],
			"tabPhoto.name"
		)

		self.assertEqual(
			extract_fieldname("count(distinct `tabPhoto`.name)")[0],
			"tabPhoto.name"
		)

		self.assertEqual(
			extract_fieldname("count(`tabPhoto`.name)")[0],
			"tabPhoto.name"
		)

		self.assertEqual(
			extract_fieldname("count(distinct `tabJob Applicant`.name) as total_count")[0],
			"tabJob Applicant.name"
		)

		self.assertEqual(
			extract_fieldname("(1 / nullif(locate('a', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name"
		)

		self.assertEqual(
			extract_fieldname("(1 / nullif(locate('(a)', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name"
		)

		self.assertEqual(
			extract_fieldname("EXTRACT(MONTH FROM date_column) AS month")[0],
			"date_column"
		)

		self.assertEqual(
			extract_fieldname("COUNT(*) AS count")[0],
			"*"
		)

		self.assertEqual(
			extract_fieldname("COUNT(1) AS count")[0],
			"*"
		)

		self.assertEqual(
			extract_fieldname("COUNT(1) AS count, SUM(1) AS sum")[0],
			"*"
		)

		self.assertEqual(
			extract_fieldname("first_name + ' ' + last_name AS full_name"),
			["first_name", "last_name"]
		)

		self.assertEqual(
			extract_fieldname("CONCAT(first_name, ' ', last_name) AS full_name"),
			["first_name", "last_name"]
		)

		self.assertEqual(
			extract_fieldname("CONCAT(id, '/', name, '/', age, '/', marks) AS student"),
			["id", "name", "age", "marks"]
		)
