# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_utils import _finalize_pdf, run_after_print_hook


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
			"frappe.utils.print_utils.run_after_print_hook", side_effect=lambda _d, _n, pdf: pdf
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

	def test_after_print_hook_returns_bytes(self):
		"""Hook may replace the PDF with new bytes."""
		todo = self._make_todo()
		original = blank_pdf()
		replacement = blank_pdf(page_count=3)

		with patch("frappe.get_cached_doc", return_value=todo):
			with patch.object(todo, "run_method", return_value=replacement) as run_method:
				result = run_after_print_hook(todo.doctype, todo.name, original)

		run_method.assert_called_once_with("after_print", pdf=original)
		self.assertEqual(result, replacement)
		self.assertEqual(len(PdfReader(io.BytesIO(result)).pages), 3)