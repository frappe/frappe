# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.doctype.document_naming_settings.document_naming_settings import (
	DocumentNamingSettings,
)
from frappe.model.naming import NamingSeries, get_default_naming_series
from frappe.tests import IntegrationTestCase
from frappe.utils import cint


class TestNamingSeries(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.ns_doctype = (
			new_doctype(
				fields=[
					{
						"label": "Series",
						"fieldname": "naming_series",
						"fieldtype": "Select",
						"options": f"\n{frappe.generate_hash()}-.###",
					}
				],
				autoname="naming_series:",
				is_submittable=1,
			)
			.insert()
			.name
		)

	def setUp(self):
		self.dns: DocumentNamingSettings = frappe.get_doc("Document Naming Settings")

	def tearDown(self):
		frappe.db.rollback()

	def get_valid_serieses(self):
		VALID_SERIES = ["SINV-", "SI-.{field}.", "SI-#.###", ""]
		existing_series = self.dns.get_transactions_and_prefixes()["prefixes"]
		return VALID_SERIES + existing_series

	def test_naming_preview(self):
		self.dns.transaction_type = self.ns_doctype

		self.dns.try_naming_series = "AXBZ.####"
		serieses = self.dns.preview_series().split("\n")
		self.assertEqual(["AXBZ0001", "AXBZ0002", "AXBZ0003"], serieses)

		self.dns.try_naming_series = "AXBZ-.{currency}.-"
		serieses = self.dns.preview_series().split("\n")

	def test_get_transactions(self):
		naming_info = self.dns.get_transactions_and_prefixes()
		self.assertIn(self.ns_doctype, naming_info["transactions"])

		existing_naming_series = frappe.get_meta(self.ns_doctype).get_field("naming_series").options

		for series in existing_naming_series.split("\n"):
			self.assertIn(NamingSeries(series).get_prefix(), naming_info["prefixes"])

	def test_default_naming_series(self):
		self.assertIsNone(get_default_naming_series("DocType"))

	def test_updates_naming_options(self):
		self.dns.transaction_type = self.ns_doctype
		test_series = "KOOHBEW.###"
		self.dns.naming_series_options = self.dns.get_options() + "\n" + test_series
		self.dns.update_series()
		self.assertIn(test_series, frappe.get_meta(self.ns_doctype).get_naming_series_options())

	def test_update_series_counter(self):
		for series in self.get_valid_serieses():
			if not series:
				continue
			self.dns.prefix = series
			current_count = cint(self.dns.get_current())
			new_count = self.dns.current_value = current_count + 1
			self.dns.update_series_start()

			self.assertEqual(self.dns.get_current(), new_count, f"Incorrect update for {series}")

	def test_amended_naming(self):
		self.dns.amend_naming_override = []
		self.dns.default_amend_naming = "Amend Counter"
		self.dns.update_amendment_rule()

		submittable_doc = frappe.get_doc(
			doctype=self.ns_doctype, some_fieldname="test doc with submit"
		).submit()
		submittable_doc.cancel()

		amended_doc = frappe.get_doc(
			doctype=self.ns_doctype, some_fieldname="test doc with submit", amended_from=submittable_doc.name
		).insert()

		self.assertIn(submittable_doc.name, amended_doc.name)
		amended_doc.delete()

		self.dns.default_amend_naming = "Default Naming"
		self.dns.update_amendment_rule()

		new_amended_doc = frappe.get_doc(
			doctype=self.ns_doctype, some_fieldname="test doc with submit", amended_from=submittable_doc.name
		).insert()
		self.assertNotIn(submittable_doc.name, new_amended_doc.name)
