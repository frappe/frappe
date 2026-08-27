# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import json
import os
import subprocess
from unittest.mock import patch

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
		from pypdf import PdfReader

		with patch.object(pinto, "render", return_value=_blank_pdf()) as render:
			pdf = pinto.get_pinto_pdf(None, "<p>hi</p>", {"password": "s3cret"}, pdf_generator="pinto")

		self.assertNotIn("password", render.call_args.args[1]["options"])
		self.assertTrue(PdfReader(io.BytesIO(pdf)).is_encrypted)

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
