# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.reportview import export_query
from frappe.tests.utils import FrappeTestCase


class TestReportview(FrappeTestCase):
	def test_csv(self):
		from csv import QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC, DictReader
		from io import StringIO

		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			title="Test Report",
			file_format_type="CSV",
		)

		for delimiter in (",", ";", "\t", "|"):
			for quoting in (QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC):
				frappe.local.form_dict.update(
					{
						"csv_quoting": quoting,
						"csv_delimiter": delimiter,
					}
				)
				export_query()

				self.assertTrue(frappe.response["filename"].endswith(".csv"))
				self.assertEqual(frappe.response["type"], "binary")
				with StringIO(frappe.response["filecontent"].decode("utf-8")) as result:
					reader = DictReader(result, delimiter=delimiter, quoting=quoting)
					reader.__next__()
