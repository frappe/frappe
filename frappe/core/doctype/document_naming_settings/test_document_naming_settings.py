# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.document_naming_settings.document_naming_settings import (
	NAMING_SERIES_PATTERN,
	DocumentNamingSettings,
)
from frappe.model.naming import get_default_naming_series
from frappe.tests.utils import FrappeTestCase


class TestNamingSeries(FrappeTestCase):
	def setUp(self):
		self.dns: DocumentNamingSettings = frappe.get_doc("Document Naming Settings")

	def tearDown(self):
		frappe.db.rollback()

	def test_naming_preview(self):
		self.dns.transaction_type = "Webhook"

		self.dns.try_naming_series = "AXBZ.####"
		serieses = self.dns.preview_series().split("\n")
		self.assertEqual(["AXBZ0001", "AXBZ0002", "AXBZ0003"], serieses)

		self.dns.try_naming_series = "AXBZ-.{currency}.-"
		serieses = self.dns.preview_series().split("\n")

	def test_get_transactions(self):

		naming_info = self.dns.get_transactions_and_prefixes()
		self.assertIn("Webhook", naming_info["transactions"])

		existing_naming_series = frappe.get_meta("Webhook").get_field("naming_series").options

		for series in existing_naming_series.split("\n"):
			self.assertIn(series, naming_info["prefixes"])

	def test_default_naming_series(self):
		self.assertIn("HOOK", get_default_naming_series("Webhook"))
		self.assertIsNone(get_default_naming_series("DocType"))
