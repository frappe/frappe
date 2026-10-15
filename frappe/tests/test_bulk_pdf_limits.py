# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import (
	download_multi_pdf,
	download_multi_pdf_async,
	get_max_bulk_print_docs,
	get_max_concurrent_bulk_exports,
)


class TestBulkPdfLimits(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(lambda: frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 0))
		self.addCleanup(
			lambda: frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 0)
		)

	def _pacing_key(self):
		return frappe.cache.make_key(f"rl:multi_pdf_async:{frappe.session.user}")

	def test_document_count_setting_is_honoured(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 3)
		self.assertEqual(get_max_bulk_print_docs(), 3)

	def test_document_count_falls_back_when_unset(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 0)
		self.assertEqual(get_max_bulk_print_docs(), 100)

	def test_request_rejected_past_document_count(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 2)
		with patch("frappe.utils.print_format._download_multi_pdf") as inner:
			with self.assertRaises(frappe.ValidationError):
				download_multi_pdf(doctype="User", name=["a", "b", "c"])
			inner.assert_not_called()

	def test_request_allowed_within_document_count(self):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 5)
		with patch("frappe.utils.print_format._download_multi_pdf", return_value="ok") as inner:
			result = download_multi_pdf(doctype="User", name=["a", "b"])
			self.assertEqual(result, "ok")
			inner.assert_called_once()

	def test_concurrent_setting_is_honoured(self):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 4)
		self.assertEqual(get_max_concurrent_bulk_exports(), 4)

	def test_pending_requests_are_paced(self):
		cache_key = self._pacing_key()
		frappe.cache.delete(cache_key)
		self.addCleanup(lambda: frappe.cache.delete(cache_key))

		with patch("frappe.utils.print_format.frappe.enqueue", return_value=MagicMock()):
			for _ in range(10):
				download_multi_pdf_async(doctype="User", name=["a"])

			with self.assertRaises(frappe.RateLimitExceededError):
				download_multi_pdf_async(doctype="User", name=["a"])

	def test_pending_slots_are_bounded(self):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 2)
		cache_key = self._pacing_key()
		frappe.cache.delete(cache_key)
		self.addCleanup(lambda: frappe.cache.delete(cache_key))

		with patch("frappe.utils.print_format.frappe.enqueue", return_value=None) as inner:
			with self.assertRaises(frappe.RateLimitExceededError):
				download_multi_pdf_async(doctype="User", name=["a"])
			self.assertEqual(inner.call_count, 2)
