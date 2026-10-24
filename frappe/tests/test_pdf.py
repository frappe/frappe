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

	def test_links_are_clickable_where_they_print_with_header_and_footer(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_chrome_pdf(
			print_format=None,
			html='<div id="header-html"><a href="https://example.com/brochure">Brochure</a></div>'
			'<a href="https://example.com/manual">Manual</a>'
			'<div id="footer-html"><b>BOTTOM</b></div>',
			options={},
			output=None,
			pdf_generator="chrome",
		)
		page = PdfReader(io.BytesIO(pdf)).pages[0]
		baselines = {}

		def record_baseline(text, cm, tm, *_):
			baselines[text.strip()] = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]

		page.extract_text(visitor_text=record_baseline)
		self.assertEqual(len(page["/Annots"]), 2)
		for annotation in page["/Annots"]:
			annotation = annotation.get_object()
			text = annotation["/A"]["/URI"].rsplit("/", 1)[1].title()
			_, bottom, _, top = annotation["/Rect"]
			self.assertGreaterEqual(baselines[text], bottom, text)
			self.assertLessEqual(baselines[text], top, text)

	def test_bulk_pdf_by_doctype_skips_a_deleted_document(self):
		from frappe.utils.print_format import _download_multi_pdf

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Call Northwind Traders"}).insert()
		deleted = frappe.get_doc({"doctype": "ToDo", "description": "Follow up with Litware"}).insert()
		deleted.delete()
		task_id = frappe.generate_hash()

		_download_multi_pdf({"ToDo": [todo.name, deleted.name]}, "ToDo", task_id=task_id)

		file = frappe.get_doc("File", {"file_name": f"ToDo_{task_id}.pdf"})
		self.assertEqual(len(PdfReader(io.BytesIO(file.get_content())).pages), 1)

	def test_smart_shrinking_is_opt_in(self):
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

	def test_network_print_raises_the_pdf_generation_error(self):
		import sys
		from unittest.mock import MagicMock, patch

		from frappe.utils import print_format

		printer = frappe.get_doc(
			doctype="Network Printer Settings",
			name="Office Printer",
			server_ip="localhost",
			port=631,
			printer_name="Office Printer",
		).insert()
		cups = MagicMock(IPPError=type("IPPError", (Exception,), {}))
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		with (
			patch.dict(sys.modules, {"cups": cups}),
			patch.object(frappe, "get_print", side_effect=ConnectionRefusedError),
			self.assertRaises(ConnectionRefusedError),
		):
			print_format.print_by_server("User", "test@example.com", printer.name)

	def test_print_styles_are_read_without_fetching_css_imports(self):
		import threading
		from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

		requested = []

		class StylesheetHandler(BaseHTTPRequestHandler):
			def do_GET(self):
				requested.append(self.path)

		server = ThreadingHTTPServer(("127.0.0.1", 0), StylesheetHandler)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		pdfgen.read_options_from_html(
			f'<style>@import url("http://127.0.0.1:{server.server_port}/print.css");</style><p>row</p>'
		)
		self.assertEqual(requested, [])

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

	def test_print_format_margin_without_a_length_is_ignored(self):
		from types import SimpleNamespace

		from bs4 import BeautifulSoup

		from frappe.utils.pdf_generator.browser import Browser

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		browser = Browser.__new__(Browser)
		browser.is_print_designer = False
		browser.print_format = None
		browser.options = {"page-size": "A4"}
		browser.soup = BeautifulSoup("<style>.print-format { margin-left: auto; }</style>", "html5lib")
		browser.body_page = SimpleNamespace(options={})
		browser.header_page = browser.footer_page = None
		browser.prepare_options_for_pdf()

		self.assertAlmostEqual(browser.body_page.options["marginLeft"], 15 / 25.4, delta=0.01)
