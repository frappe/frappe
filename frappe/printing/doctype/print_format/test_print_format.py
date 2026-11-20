# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import re
import unittest
from typing import TYPE_CHECKING
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.print_format import _download_multi_pdf

if TYPE_CHECKING:
	from frappe.printing.doctype.print_format.print_format import PrintFormat

test_records = frappe.get_test_records("Print Format")


class TestPrintFormat(FrappeTestCase):
	def test_print_user(self, style=None):
		print_html = frappe.get_print("User", "Administrator", style=style)
		self.assertTrue("<label>First Name: </label>" in print_html)
		self.assertTrue(re.findall(r'<div class="col-xs-[^"]*">[\s]*administrator[\s]*</div>', print_html))
		return print_html

	def test_print_user_standard(self):
		print_html = self.test_print_user("Standard")
		self.assertTrue(re.findall(r"\.print-format {[\s]*font-size: 9pt;", print_html))
		self.assertFalse(re.findall(r"th {[\s]*background-color: #eee;[\s]*}", print_html))
		self.assertFalse("font-family: serif;" in print_html)

	def test_print_user_modern(self):
		print_html = self.test_print_user("Modern")
		self.assertTrue("/* modern format: for-test */" in print_html)

	def test_print_user_classic(self):
		print_html = self.test_print_user("Classic")
		self.assertTrue("/* classic format: for-test */" in print_html)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	def test_export_doc(self):
		doc: PrintFormat = frappe.get_doc("Print Format", test_records[0]["name"])

		# this is only to make export_doc happy
		doc.standard = "Yes"
		_before = frappe.conf.developer_mode
		frappe.conf.developer_mode = True
		export_path = doc.export_doc()
		frappe.conf.developer_mode = _before

		exported_doc_path = f"{export_path}.json"
		doc.reload()
		doc_dict = doc.as_dict(no_nulls=True, convert_dates_to_str=True)

		self.assertTrue(os.path.exists(exported_doc_path))

		with open(exported_doc_path) as f:
			exported_doc = frappe.parse_json(f.read())

		for key, value in exported_doc.items():
			if key in doc_dict:
				with self.subTest(key=key):
					self.assertEqual(value, doc_dict[key])

		self.addCleanup(os.remove, exported_doc_path)


class TestBulkPrintLanguage(FrappeTestCase):
	def setUp(self):
		frappe.db.set_value("User", "Administrator", "language", "de")
		frappe.db.set_value("User", "Guest", "language", None)
		self.print_format = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "_Test Bulk Print Language",
				"doc_type": "User",
				"standard": "No",
				"default_print_language": "fr",
			}
		).insert(ignore_if_duplicate=True)

		original_lang = frappe.local.lang
		frappe.local.lang = "en"
		self.addCleanup(setattr, frappe.local, "lang", original_lang)

	def bulk_print(self, names, fail_for=(), **kwargs):
		"""Run a bulk print and return the language each document was printed in."""
		printed_in = {}

		def fake_get_print(doctype, name, *args, **print_kwargs):
			printed_in[name] = frappe.local.lang
			if name in fail_for:
				raise frappe.PermissionError
			return print_kwargs["output"]

		with patch("frappe.get_print", side_effect=fake_get_print):
			_download_multi_pdf("User", json.dumps(names), **kwargs)

		return printed_in

	def test_format_language_is_used(self):
		printed_in = self.bulk_print(["Guest"], format=self.print_format.name)
		self.assertEqual(printed_in["Guest"], "fr")

	def test_document_language_wins_over_format_language(self):
		printed_in = self.bulk_print(["Administrator"], format=self.print_format.name)
		self.assertEqual(printed_in["Administrator"], "de")

	def test_language_is_restored_after_failed_document(self):
		printed_in = self.bulk_print(["Administrator", "Guest"], fail_for=["Administrator"])
		self.assertEqual(printed_in["Administrator"], "de")
		self.assertEqual(printed_in["Guest"], "en")
		self.assertEqual(frappe.local.lang, "en")

	def test_request_language_is_used_as_fallback(self):
		"""The background job passes the language of the request."""
		printed_in = self.bulk_print(["Guest"], language="es")
		self.assertEqual(printed_in["Guest"], "es")
