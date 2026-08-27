# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import json
import os
import subprocess
from unittest.mock import patch

from pypdf import PdfReader

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.pdf_generator import pinto

MINIMAL_PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class TestPintoPdf(IntegrationTestCase):
	def test_hook_ignores_other_generators(self):
		for generator in ("wkhtmltopdf", "chrome", "Typst", None):
			with patch.object(pinto, "render") as render:
				self.assertIsNone(pinto.get_pinto_pdf("Standard", "<p>hi</p>", {}, pdf_generator=generator))
				render.assert_not_called()

	def test_hook_ignores_html_less_dispatch(self):
		"""Beta formats dispatch without HTML and stay on Chromium."""
		with patch.object(pinto, "render") as render:
			self.assertIsNone(pinto.get_pinto_pdf("Standard", None, {}, pdf_generator="pinto"))
			render.assert_not_called()

	def test_missing_binary_throws(self):
		with patch.dict(frappe.conf, {"pinto_path": "/nonexistent/pinto"}):
			self.assertRaises(pinto.PintoNotFound, pinto.get_pinto_path)

	def test_config_carries_site_paths_and_page_defaults(self):
		config = pinto.build_config(None, {"orientation": "Landscape"})

		self.assertEqual(config["options"], {"orientation": "Landscape"})
		self.assertFalse(config["is_print_designer"])
		self.assertTrue(config["host_url"])
		self.assertTrue(os.path.isdir(config["bench_sites_path"]))
		self.assertTrue(config["default_page_size"])
		json.dumps(config)

	def test_password_is_applied_by_frappe_not_pinto(self):
		"""pinto's own encryption silently no-ops without qpdf, so Frappe encrypts."""
		with patch.object(pinto, "render", return_value=_blank_pdf()) as render:
			pdf = pinto.get_pinto_pdf(None, "<p>hi</p>", {"password": "s3cret"}, pdf_generator="pinto")

		self.assertNotIn("password", render.call_args.args[1]["options"])
		self.assertTrue(PdfReader(io.BytesIO(pdf)).is_encrypted)

	def test_output_writer_gets_unencrypted_pages(self):
		"""print_utils merges returned bytes into the writer, which cannot read an encrypted PDF."""
		from pypdf import PdfWriter

		with patch.object(pinto, "render", return_value=_blank_pdf()):
			pdf = pinto.get_pinto_pdf(
				None, "<p>hi</p>", {"password": "s3cret"}, output=PdfWriter(), pdf_generator="pinto"
			)

		self.assertFalse(PdfReader(io.BytesIO(pdf)).is_encrypted)

	def test_custom_page_size_becomes_explicit_mm_dimensions(self):
		print_settings = frappe.get_cached_doc("Print Settings")
		print_settings.pdf_page_size = "Custom"
		print_settings.pdf_page_height = 100
		print_settings.pdf_page_width = 200.5

		page_size, dimensions = pinto.resolve_page_size(print_settings, {})

		self.assertNotEqual(page_size, "Custom")
		self.assertEqual(dimensions, {"page-height": "100mm", "page-width": "200.5mm"})

	def test_explicit_page_size_passes_through(self):
		print_settings = frappe.get_cached_doc("Print Settings")
		print_settings.pdf_page_size = "Custom"

		self.assertEqual(pinto.resolve_page_size(print_settings, {"page-size": "Letter"}), ("Letter", {}))

	def test_with_unit_keeps_existing_units(self):
		self.assertEqual(pinto.with_unit(210), "210mm")
		self.assertEqual(pinto.with_unit("8.5in"), "8.5in")

	def test_private_images_are_inlined(self):
		with (
			patch.object(pinto, "render", return_value=_blank_pdf()),
			patch.object(pinto, "inline_private_images", side_effect=lambda html: html) as inline,
		):
			pinto.get_pinto_pdf(None, "<p>hi</p>", {}, pdf_generator="pinto")

		inline.assert_called_once_with("<p>hi</p>")

	def test_selecting_pinto_without_the_binary_is_rejected_on_save(self):
		"""Fail on save, not on every later download/attachment/auto-email."""
		print_settings = frappe.get_doc("Print Settings")
		print_settings.pdf_generator = "pinto"

		with patch.dict(frappe.conf, {"pinto_path": "/nonexistent/pinto"}):
			self.assertRaises(pinto.PintoNotFound, print_settings.validate)

	def test_migrate_does_not_fail_on_a_missing_binary(self):
		from frappe.utils.print_utils import validate_pdf_generator

		frappe.flags.in_migrate = True
		try:
			with patch.dict(frappe.conf, {"pinto_path": "/nonexistent/pinto"}):
				validate_pdf_generator("pinto")
		finally:
			frappe.flags.in_migrate = False

	def test_render_reports_binary_failure(self):
		error = subprocess.CalledProcessError(1, "pinto", stderr=b"Error: parsing options JSON")

		with (
			patch.object(pinto, "get_pinto_path", return_value="/bin/true"),
			patch("subprocess.run", side_effect=error),
		):
			with self.assertRaises(pinto.PintoRenderError):
				pinto.render("<p>hi</p>", {})

	def test_render_rejects_non_pdf_output(self):
		completed = subprocess.CompletedProcess([], 0, stdout=b"not a pdf", stderr=b"")

		with (
			patch.object(pinto, "get_pinto_path", return_value="/bin/true"),
			patch("subprocess.run", return_value=completed),
		):
			with self.assertRaises(pinto.PintoRenderError):
				pinto.render("<p>hi</p>", {})

	def test_render_pipes_html_on_stdin(self):
		completed = subprocess.CompletedProcess([], 0, stdout=MINIMAL_PDF, stderr=b"")

		with (
			patch.object(pinto, "get_pinto_path", return_value="/bin/true"),
			patch("subprocess.run", return_value=completed) as run,
		):
			self.assertEqual(pinto.render("<p>hi</p>", {"options": {}}), MINIMAL_PDF)

		argv = run.call_args.args[0]
		self.assertEqual(run.call_args.kwargs["input"], b"<p>hi</p>")
		self.assertEqual(argv[:2], ["/bin/true", "--html"])
		self.assertEqual(argv[2], "-")
		self.assertEqual(argv[3], "--options")
		self.assertTrue(argv[4].endswith("config.json"))
		self.assertEqual(argv[5:], ["--out", "-"])


def _blank_pdf() -> bytes:
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=100, height=100)
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()
