# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.patches.v16_0.backfill_print_settings_bulk_export_limits import execute as backfill_limits
from frappe.tests import IntegrationTestCase


class TestPrintSettings(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_backfill_limits_ignores_stale_pdf_generator(self):
		# sites that predate the wkhtmltopdf removal still carry the old value
		frappe.db.set_single_value("Print Settings", "pdf_generator", "wkhtmltopdf")
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 0)
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 0)

		backfill_limits()

		self.assertEqual(frappe.db.get_single_value("Print Settings", "max_bulk_print_docs"), 100)
		self.assertEqual(frappe.db.get_single_value("Print Settings", "max_concurrent_bulk_exports"), 5)

	def test_backfill_limits_keeps_existing_values(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 20)
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 2)

		backfill_limits()

		self.assertEqual(frappe.db.get_single_value("Print Settings", "max_bulk_print_docs"), 20)
		self.assertEqual(frappe.db.get_single_value("Print Settings", "max_concurrent_bulk_exports"), 2)
