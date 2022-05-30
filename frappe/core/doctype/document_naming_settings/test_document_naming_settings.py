# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.document_naming_settings.document_naming_settings import (
	DocumentNamingSettings,
)
from frappe.tests.utils import FrappeTestCase


class TestNamingSeries(FrappeTestCase):
	def setUp(self):
		self.ns: DocumentNamingSettings = frappe.get_doc("Naming Series Settings")

	def tearDown(self):
		frappe.db.rollback()

	def test_naming_preview(self):
		self.ns.transaction_type = "Sales Invoice"

		self.ns.try_naming_series = "AXBZ.####"
		serieses = self.ns.preview_series().split("\n")
		self.assertEqual(["AXBZ0001", "AXBZ0002", "AXBZ0003"], serieses)

		self.ns.try_naming_series = "AXBZ-.{currency}.-"
		serieses = self.ns.preview_series().split("\n")

	def test_get_transactions(self):

		naming_info = self.ns.get_transactions()
		self.assertIn("Sales Invoice", naming_info["transactions"])

		existing_naming_series = frappe.get_meta("Sales Invoice").get_field("naming_series").options

		for series in existing_naming_series.split("\n"):
			self.assertIn(series, naming_info["prefixes"])
