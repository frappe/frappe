# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io

from pypdf import PdfReader

import frappe
import frappe.utils.pdf as pdfgen
from frappe.core.doctype.file.test_file import make_test_image_file
from frappe.tests import IntegrationTestCase


def blank_pdf() -> bytes:
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


class TestPdf(IntegrationTestCase):
	@property
	def html(self):
		return """<style>
			.print-format {
			 margin-top: 0mm;
			 margin-left: 10mm;
			 margin-right: 0mm;
			}
			</style>
			<p>This is a test html snippet</p>
			<div class="more-info">
				<a href="http://test.com">Test link 1</a>
				<a href="/about">Test link 2</a>
				<a href="login">Test link 3</a>
				<img src="/assets/frappe/test.jpg">
			</div>
			<div style="background-image: url('/assets/frappe/bg.jpg')">
				Please mail us at <a href="mailto:test@example.com">email</a>
			</div>"""

	def runTest(self):
		self.test_read_options_from_html()

	def test_read_options_from_html(self):
		_, html_options = pdfgen.read_options_from_html(self.html)
		self.assertTrue(html_options["margin-top"] == "0")
		self.assertTrue(html_options["margin-left"] == "10mm")
		self.assertTrue(html_options["margin-right"] == "0")

		html_1 = """<style>
			.print-format {
				margin-top: 0mm;
				margin-left: 10mm;
			}
			.print-format .more-info {
				margin-right: 15mm;
			}
			.print-format, .more-info {
				margin-bottom: 20mm;
			}
			</style>
			<div class="more-info">Hello</div>
		"""
		_, options = pdfgen.read_options_from_html(html_1)

		self.assertTrue(options["margin-top"] == "0")
		self.assertTrue(options["margin-left"] == "10mm")
		self.assertTrue(options["margin-bottom"] == "20mm")
		# margin-right was for .more-info (child of .print-format)
		# so it should not be extracted into options
		self.assertFalse(options.get("margin-right"))

	def test_empty_style(self):
		html = """<style></style>
			<div class="more-info">Hello</div>
		"""
		_, options = pdfgen.read_options_from_html(html)
		self.assertTrue(options)

	def test_pdf_encryption(self):
		password = "qwe"
		pdf = pdfgen.get_pdf(self.html, options={"password": password})
		reader = PdfReader(io.BytesIO(pdf))
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt(password))

<<<<<<< HEAD
	def test_smart_shrinking_is_opt_in(self):
=======
	def test_password_with_output_writer_appends_pages(self):
		from pypdf import PdfWriter

		output = pdfgen.get_pdf("<p>first</p>", options={"password": "qwe"}, output=PdfWriter())
		self.assertEqual(len(output.pages), 1)

	def test_repeated_header_marked_hidden_pdf_still_prints(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_pdf(
			'<div id="header-html" class="hidden-pdf"><b>REPORT HEADER</b></div><p>report body</p>'
		)
		text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
		self.assertIn("REPORT HEADER", text)
		self.assertIn("report body", text)

	def test_empty_header_and_footer_are_skipped(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_pdf(
			'<div id="header-html" class="hidden-pdf"></div><p>body text</p><div id="footer-html"></div>'
		)
		self.assertIn("body text", PdfReader(io.BytesIO(pdf)).pages[0].extract_text())

	def test_print_format_margins_keep_header_and_footer_on_every_page(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		rows = "".join(f"<p>row {i}</p>" for i in range(150))
		pdf = pdfgen.get_pdf(
			"<style>.print-format { margin-top: 30mm; margin-bottom: 20mm; }</style>"
			'<div class="print-format"><div id="header-html"><b>TOP</b></div>'
			f"{rows}"
			'<div id="footer-html">Page <span class="page"></span> of <span class="topage"></span></div></div>'
		)
		pages = PdfReader(io.BytesIO(pdf)).pages
		self.assertGreater(len(pages), 1)
		for number, page in enumerate(pages, start=1):
			text = page.extract_text()
			self.assertIn("TOP", text)
			self.assertIn(f"Page {number} of {len(pages)}", text)

	def test_bulk_pdf_with_password_keeps_every_document(self):
		import json

		from frappe.utils.print_format import _download_multi_pdf

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		names = [
			frappe.get_doc({"doctype": "ToDo", "description": f"bulk {i}"}).insert().name for i in range(2)
		]

		_download_multi_pdf(
			"ToDo", json.dumps(names), format="Standard", options=json.dumps({"password": "qwe"})
		)

		reader = PdfReader(io.BytesIO(frappe.local.response.filecontent))
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt("qwe"))
		self.assertGreaterEqual(len(reader.pages), 2)

	def test_large_pdf_is_optimized_before_encryption(self):
		import os

		from PIL import Image

		path = frappe.get_site_path("public", "files", "_test_large_photo.jpg")
		Image.effect_noise((3000, 3000), 80).convert("RGB").save(path, quality=95)
		self.addCleanup(os.remove, path)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		html = '<p>photo</p><img src="/files/_test_large_photo.jpg" style="width: 80px">'
		self.assertLess(len(pdfgen.get_pdf(html)), pdfgen.LARGE_PDF_SIZE)

		reader = PdfReader(io.BytesIO(pdfgen.get_pdf(html, {"password": "qwe"})))
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt("qwe"))

	def test_large_pdf_without_images_is_not_optimized(self):
		from unittest.mock import patch

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		with (
			patch.object(pdfgen, "LARGE_PDF_SIZE", 0),
			patch.object(pdfgen, "optimize_pdf") as optimize_pdf,
		):
			pdfgen.get_pdf("<p>Renew the example.com domain</p>")

		optimize_pdf.assert_not_called()

	def test_large_pdf_with_translucent_image_is_optimized(self):
		import os

		from PIL import Image

		path = frappe.get_site_path("public", "files", "_test_translucent_photo.jpg")
		Image.effect_noise((3000, 3000), 80).convert("RGB").save(path, quality=95)
		self.addCleanup(os.remove, path)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		html = '<img src="/files/_test_translucent_photo.jpg" style="width: 80px; opacity: 0.5">'
		self.assertLess(len(pdfgen.get_pdf(html)), pdfgen.LARGE_PDF_SIZE)

	def test_pdf_visibility_classes_apply_to_the_body(self):
		pdf = pdfgen.get_pdf(
			"<style>.visible-pdf { display: none; }</style>"
			'<p class="hidden-pdf">screen only</p><p class="visible-pdf">pdf only</p>'
		)
		text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
		self.assertIn("pdf only", text)
		self.assertNotIn("screen only", text)

	def test_on_print_pdf_hook_runs_for_chrome_prints(self):
>>>>>>> 89c0462 (test(pdf): large pdfs without images skip optimization)
		from unittest.mock import patch

		captured = {}

		def capture_options(html, options=None, verbose=True):
			captured.clear()
			captured.update(options or {})
			return blank_pdf()

		with (
			patch.object(pdfgen.pdfkit, "from_string", side_effect=capture_options),
			patch.object(pdfgen, "get_wkhtmltopdf_version", return_value="0.12.6"),
		):
			pdfgen.get_pdf(self.html)
			self.assertIn("disable-smart-shrinking", captured)

			pdfgen.get_pdf(self.html, smart_shrinking=True)
			self.assertNotIn("disable-smart-shrinking", captured)

	def test_report_pdf_is_scaled_to_fit_the_page(self):
		from unittest.mock import patch

		from frappe.utils import print_format

		with patch.object(print_format, "get_pdf", return_value=blank_pdf()) as get_report_pdf:
			print_format.report_to_pdf("<table><tr><td>a wide report</td></tr></table>")

		self.assertTrue(get_report_pdf.call_args.kwargs["smart_shrinking"])

	def test_pdf_generation_as_a_user(self):
		frappe.set_user("Administrator")
		pdf = pdfgen.get_pdf(self.html)
		self.assertTrue(pdf)

	def test_private_images_in_pdf(self):
		with make_test_image_file(private=True) as file:
			html = f""" <div>
				<img src="{file.file_url}" class='responsive'>
				<img src="{file.unique_url}" class='responsive'>
			</div>
			"""

			pdf = pdfgen.get_pdf(html)

		# If image was actually retrieved then size will be  in few kbs, else bytes.
		self.assertGreaterEqual(len(pdf), 10_000)
