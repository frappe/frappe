# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import (
	classic_page_options,
	download_multi_pdf,
	download_multi_pdf_async,
	get_max_bulk_print_docs,
	get_max_concurrent_bulk_exports,
	page_settings,
)


class TestBulkPdfLimits(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(lambda: frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 0))
		self.addCleanup(
			lambda: frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 0)
		)

	def _pacing_key(self):
		return frappe.cache.make_key(f"rl:multi_pdf_async:{frappe.session.user}")

	def test_bulk_pdf_uses_the_formats_default_print_language(self):
		import json

		from pypdf import PdfWriter

		from frappe.utils.print_format import _download_multi_pdf

		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type="User",
			custom_format=1,
			print_format_type="Jinja",
			html="{{ doc.name }}",
			default_print_language="de",
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)
		seen = []

		def fake_get_print(*args, **kwargs):
			seen.append(frappe.local.lang)
			kwargs["output"].add_blank_page(width=72, height=72)
			return kwargs["output"]

		with patch("frappe.get_print", side_effect=fake_get_print):
			_download_multi_pdf("User", json.dumps(["Administrator"]), pf.name)

		self.assertEqual(seen, ["de"])
		self.assertEqual(frappe.local.lang, "en")

	def test_bulk_pdf_sends_typst_builder_formats_through_the_generator(self):
		import json
		from io import BytesIO

		from pypdf import PdfWriter

		from frappe.utils.print_format import _download_multi_pdf

		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type="ToDo",
			print_format_builder_beta=1,
			pdf_generator="Typst",
			format_data="{}",
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)
		todo = frappe.get_doc(doctype="ToDo", description="typst bulk").insert()
		blank = BytesIO()
		writer = PdfWriter()
		writer.add_blank_page(width=72, height=72)
		writer.write(blank)

		with (
			patch(
				"frappe.utils.print_format_generator.PrintFormatGenerator.render_pdf",
				return_value=blank.getvalue(),
			) as render_pdf,
			patch("frappe.get_print") as get_print,
			patch.object(frappe.local, "response", frappe._dict()),
		):
			_download_multi_pdf("ToDo", json.dumps([todo.name]), pf.name)
			self.assertTrue(frappe.local.response.filecontent)

		render_pdf.assert_called_once()
		get_print.assert_not_called()

	def test_page_settings_map_the_dialogs_page_choice(self):
		self.assertEqual(page_settings(None), {})
		self.assertEqual(page_settings({"password": "x"}), {})
		self.assertEqual(page_settings({"page-size": "Letter"}), {"pdf_page_size": "Letter"})
		self.assertEqual(
			page_settings({"page-height": "100mm", "page-width": "50mm"}),
			{"pdf_page_size": "Custom", "pdf_page_height": "100mm", "pdf_page_width": "50mm"},
		)

	def test_classic_page_options_carry_the_dialogs_custom_size_in_mm(self):
		self.assertEqual(classic_page_options(None), {})
		self.assertEqual(classic_page_options({"page-size": "A5"}), {"page-size": "A5"})
		self.assertEqual(
			classic_page_options({"page-height": 100, "page-width": 50.5, "password": "x"}),
			{"page-size": "Custom", "page-height": "100mm", "page-width": "50.5mm", "password": "x"},
		)
		self.assertEqual(
			classic_page_options({"page-height": "100mm", "page-width": "50mm"}),
			{"page-height": "100mm", "page-width": "50mm"},
		)

	def test_bulk_pdf_hands_classic_formats_the_custom_size_with_a_unit(self):
		import json

		from frappe.utils.print_format import _download_multi_pdf

		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type="User",
			custom_format=1,
			print_format_type="Jinja",
			html="{{ doc.name }}",
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)
		seen = []

		def fake_get_print(*args, **kwargs):
			seen.append(kwargs["pdf_options"])
			kwargs["output"].add_blank_page(width=72, height=72)
			return kwargs["output"]

		options = json.dumps({"page-height": 100, "page-width": 50})
		with patch("frappe.get_print", side_effect=fake_get_print):
			_download_multi_pdf("User", json.dumps(["Administrator"]), pf.name, options=options)

		self.assertEqual(seen, [{"page-size": "Custom", "page-height": "100mm", "page-width": "50mm"}])

	def test_bulk_pdf_tells_the_requester_when_a_permission_check_fails(self):
		import json

		from frappe.utils.print_format import _download_multi_pdf

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with patch("frappe.publish_realtime") as publish:
			with self.assertRaises(frappe.PermissionError):
				_download_multi_pdf("User", json.dumps(["Administrator"]), None, task_id="bulk-test")
		publish.assert_called_once()
		self.assertEqual(publish.call_args.args[0], "task_complete:bulk-test")
		self.assertTrue(publish.call_args.kwargs["message"]["error"])
		self.assertEqual(publish.call_args.kwargs["user"], "Guest")

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
