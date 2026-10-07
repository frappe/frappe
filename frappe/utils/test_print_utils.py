# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io
from unittest.mock import MagicMock, patch

from pypdf import PdfReader, PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format_generator import PrintFormatGenerator
from frappe.utils.print_utils import _finalize_pdf, get_print, run_after_print_hook


def blank_pdf(page_count=1) -> bytes:
	writer = PdfWriter()
	for _ in range(page_count):
		writer.add_blank_page(width=72, height=72)
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def pdf_writer(page_count=1) -> PdfWriter:
	writer = PdfWriter()
	for _ in range(page_count):
		writer.add_blank_page(width=72, height=72)
	return writer


def mark_before_print(doc, method, print_settings=None):
	doc.flags.prepared_for_print = doc.name


def replace_pdf_after_print(doc, method, pdf=None):
	frappe.flags.print_hook = {
		"marker": doc.flags.get("prepared_for_print"),
		"doc_id": id(doc),
	}
	if doc.flags.get("prepared_for_print") != doc.name:
		return pdf
	return blank_pdf(page_count=3)


class TestPrintUtils(IntegrationTestCase):
	def _make_todo(self):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "print utils test"})
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	def test_finalize_pdf_accepts_pdfwriter(self):
		"""PdfWriter input is converted to bytes before the after_print hook runs."""
		todo = self._make_todo()
		writer = pdf_writer()

		with patch(
			"frappe.utils.print_utils.run_after_print_hook",
			side_effect=lambda _d, _n, pdf, **_: pdf,
		) as hook:
			result = _finalize_pdf(todo.doctype, todo.name, writer)

		self.assertIsInstance(result, bytes)
		self.assertEqual(len(PdfReader(io.BytesIO(result)).pages), 1)
		hook.assert_called_once()
		self.assertIsInstance(hook.call_args.args[2], bytes)

	def test_finalize_pdf_appends_to_output(self):
		"""When output=PdfWriter is given, hook-processed pages are appended."""
		todo = self._make_todo()
		output = PdfWriter()
		output.add_blank_page(width=72, height=72)

		hook_pdf = blank_pdf(page_count=2)
		with patch("frappe.utils.print_utils.run_after_print_hook", return_value=hook_pdf):
			result = _finalize_pdf(todo.doctype, todo.name, blank_pdf(), output=output)

		self.assertIs(result, output)
		self.assertEqual(len(result.pages), 3)

	def test_before_and_after_print_share_the_doc(self):
		todo = self._make_todo()
		frappe.flags.print_hook = {}
		self.addCleanup(lambda: setattr(frappe.local, "doc_events_hooks", None))

		with self.patch_hooks(
			{
				"doc_events": {
					"ToDo": {
						"before_print": "frappe.utils.test_print_utils.mark_before_print",
						"after_print": "frappe.utils.test_print_utils.replace_pdf_after_print",
					}
				}
			}
		):
			frappe.local.doc_events_hooks = None
			from frappe.www.printview import run_before_print

			run_before_print(todo, {})

			# doc= skips print_doc; the passed object already carries the marker
			with_doc = run_after_print_hook(todo.doctype, todo.name, blank_pdf(), doc=todo)
			self.assertEqual(frappe.flags.print_hook["marker"], todo.name)
			self.assertEqual(frappe.flags.print_hook["doc_id"], id(todo))
			self.assertEqual(len(PdfReader(io.BytesIO(with_doc)).pages), 3)

			# no doc: get_cached_doc has no marker, so the PDF stays 1 page
			from_cache = run_after_print_hook(todo.doctype, todo.name, blank_pdf())
			self.assertIsNone(frappe.flags.print_hook["marker"])
			self.assertNotEqual(frappe.flags.print_hook["doc_id"], id(todo))
			self.assertEqual(len(PdfReader(io.BytesIO(from_cache)).pages), 1)

	def test_after_print_runs_for_all_pdf_backends(self):
		"""after_print must run on wkhtmltopdf, Chrome, and Typst paths."""

		todo = self._make_todo()
		pdf = blank_pdf()

		mock_hook = MagicMock(side_effect=lambda _d, _n, p, **_: p)
		with (
			patch("frappe.utils.print_utils.run_after_print_hook", mock_hook),
			patch("frappe.utils.print_format_generator.run_after_print_hook", mock_hook),
		):
			with (
				patch(
					"frappe.website.serve.get_response_without_exception_handling",
					return_value=type("R", (), {"data": b"<html></html>"})(),
				),
				patch("frappe.utils.pdf.get_pdf", return_value=pdf),
			):
				get_print(todo.doctype, todo.name, as_pdf=True, pdf_generator="wkhtmltopdf")

			passed = mock_hook.call_args.kwargs["doc"]
			self.assertEqual((passed.doctype, passed.name), (todo.doctype, todo.name))

			self.assertEqual(mock_hook.call_count, 1)

			pf = frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": f"_Test {frappe.generate_hash(length=6)}",
					"doc_type": "ToDo",
					"print_format_builder_beta": 1,
					"format_data": '{"sections": [], "header": {"columns": []}, "footer": {"columns": []}}',
				}
			).insert(ignore_permissions=True)
			self.addCleanup(pf.delete, ignore_permissions=True)

			generator = PrintFormatGenerator(pf, todo)
			with patch("frappe.utils.pdf.get_chrome_pdf", return_value=pdf):
				generator.render_pdf()
			mock_hook.assert_called_with(todo.doctype, todo.name, pdf, doc=todo)

			self.assertEqual(mock_hook.call_count, 2)

			pf.db_set("pdf_generator", "Typst")
			generator = PrintFormatGenerator(pf, todo)
			with patch.object(generator, "render_typst_pdf", return_value=pdf):
				generator.render_pdf()
			mock_hook.assert_called_with(todo.doctype, todo.name, pdf, doc=todo)

			self.assertEqual(mock_hook.call_count, 3)
