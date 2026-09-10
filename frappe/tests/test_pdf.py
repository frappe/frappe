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


class TestChromePdfGeometry(IntegrationTestCase):
	"""Unit tests for Browser paper geometry — no chromium process involved."""

	def make_browser(self, options, header_height=None, footer_height=None):
		from types import SimpleNamespace

		from bs4 import BeautifulSoup

		from frappe.utils.pdf_generator.browser import Browser

		browser = Browser.__new__(Browser)
		browser.is_print_designer = False
		browser.options = options
		browser.soup = BeautifulSoup("<html><head></head><body></body></html>", "html5lib")
		browser.body_page = SimpleNamespace(options={})
		browser.header_page = SimpleNamespace(options={}) if header_height is not None else None
		browser.footer_page = SimpleNamespace(options={}) if footer_height is not None else None
		if header_height is not None:
			browser.header_height = header_height
		if footer_height is not None:
			browser.footer_height = footer_height
		return browser

	def test_custom_page_size_converted_from_mm(self):
		from frappe.tests.classes.context_managers import change_settings

		with change_settings(
			"Print Settings", pdf_page_size="Custom", pdf_page_height=297, pdf_page_width=210
		):
			browser = self.make_browser({})
			browser.prepare_options_for_pdf()

		# 210x297mm must match A4 in inches, not be consumed as px
		self.assertAlmostEqual(browser.body_page.options["paperWidth"], 8.27, delta=0.05)
		self.assertAlmostEqual(browser.body_page.options["paperHeight"], 11.69, delta=0.05)

	def test_custom_page_size_without_dimensions_raises(self):
		from unittest.mock import patch

		# Print Settings validation forbids zero dimensions, so this state is only
		# reachable when print CSS declares page-size: Custom without dimensions
		browser = self.make_browser({"page-size": "Custom"})
		with patch.object(frappe.db, "get_single_value", return_value=None):
			self.assertRaisesRegex(
				frappe.ValidationError, "Custom page size", browser.prepare_options_for_pdf
			)

	def test_header_spacing_parsed_from_css_string(self):
		from frappe.utils.print_utils import convert_uom

		for spacing in ("5mm", "5"):
			browser = self.make_browser({"page-size": "A4", "header-spacing": spacing}, header_height=100)
			browser.prepare_options_for_pdf()
			expected = convert_uom(
				100 + convert_uom(5, "mm", "px", only_number=True), "px", "in", only_number=True
			)
			self.assertAlmostEqual(browser.header_page.options["paperHeight"], expected, delta=0.01)

	def test_oversized_header_footer_raises(self):
		browser = self.make_browser({"page-size": "A4"}, header_height=1000, footer_height=300)
		self.assertRaisesRegex(frappe.ValidationError, "no room for content", browser.prepare_options_for_pdf)


class TestChromeCdpReliability(IntegrationTestCase):
	"""Unit tests for CDP failure handling — no chromium process involved."""

	def make_client(self):
		from frappe.utils.chromium.cdp_connection import CDPSocketClient

		client = CDPSocketClient("ws://never-connected")
		self.addCleanup(client.loop.close)
		return client

	def test_fail_pending_messages_resolves_inflight_commands(self):
		client = self.make_client()
		future = client.loop.create_future()
		client.pending_messages = {1: future, ("Page.printToPDF", None, None, None): future}

		client._fail_pending_messages()

		self.assertTrue(future.done())
		self.assertIsInstance(future.exception(), ConnectionError)
		self.assertFalse(client.pending_messages)

	def test_send_times_out_when_chromium_never_responds(self):
		class FakeConnection:
			async def send(self, message):
				pass

		client = self.make_client()
		client.connection = FakeConnection()
		client.COMMAND_TIMEOUT = 0.05

		with self.assertRaisesRegex(TimeoutError, "did not respond"):
			client.loop.run_until_complete(client._send("Page.printToPDF"))
		self.assertFalse(client.pending_messages)

	def test_evaluate_returns_result_when_retry_succeeds(self):
		from unittest.mock import patch

		from frappe.utils.chromium.page import Page

		class FakeSession:
			def __init__(self, script):
				self.script = script

			def send(self, method, params=None, session_id=None, return_future=False):
				if method == "Runtime.evaluate":
					return self.script.pop(0)
				return {}, None

		page = Page.__new__(Page)
		page.session_id = "sid"
		page.session = FakeSession([(None, {"message": "boom"}), ({"result": {"value": 2}}, None)])

		with patch("frappe.utils.chromium.page.time.sleep"):
			result = page.evaluate("1+1")
		self.assertEqual(result["result"]["value"], 2)

		page.session = FakeSession([(None, {"message": "boom"})] * 4)
		with patch("frappe.utils.chromium.page.time.sleep"):
			self.assertRaisesRegex(RuntimeError, "Error evaluating expression", page.evaluate, "1+1")


class TestPdfResourceUrlGuard(IntegrationTestCase):
	"""Unit tests for guard_pdf_resource_urls — no wkhtmltopdf process involved.

	Addresses used here are numeric IP literals so the check never depends on
	real DNS/network being reachable from the test environment.
	"""

	def test_blocks_loopback_and_link_local(self):
		html = '<img src="http://127.0.0.1:9999/probe.png"><img src="http://169.254.169.254/meta">'
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertNotIn("127.0.0.1:9999", guarded)
		self.assertNotIn("169.254.169.254", guarded)

	def test_blocks_private_range_in_css_url(self):
		html = "<div style=\"background-image:url('http://10.1.2.3/probe.png')\"></div>"
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertNotIn("10.1.2.3", guarded)
		self.assertIn("url('')", guarded)

	def test_blocks_css_import_and_font_face(self):
		html = (
			"<style>@import url(http://10.1.2.3/x.css);@font-face{src:url('http://10.1.2.3/f.woff')}</style>"
		)
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertNotIn("10.1.2.3", guarded)

	def test_allows_public_address(self):
		html = '<img src="http://8.8.8.8/probe.png"><div style="background-image:url(http://8.8.8.8/bg.png)"></div>'
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertEqual(guarded.count("8.8.8.8"), 2)

	def test_trusted_domain_bypasses_resolution(self):
		from unittest.mock import patch

		# A domain that won't resolve — proves the trusted-host check short-circuits
		# before any DNS lookup, not merely that the address happens to be public.
		with patch.dict(frappe.conf, {"domains": ["trusted-external.invalid"]}):
			guarded = pdfgen.guard_pdf_resource_urls('<img src="http://trusted-external.invalid/logo.png">')
		self.assertIn("trusted-external.invalid", guarded)

	def test_blocked_url_is_logged(self):
		frappe.db.delete("Error Log", {"method": "Blocked internal PDF resource URL"})
		pdfgen.guard_pdf_resource_urls('<img src="http://127.0.0.1:9998/marker.png">')
		self.assertTrue(
			frappe.db.exists(
				"Error Log",
				{"method": "Blocked internal PDF resource URL", "error": ["like", "%127.0.0.1:9998%"]},
			)
		)

	def test_blocks_uppercase_scheme(self):
		# URL schemes are case-insensitive by spec; a renderer still fetches "HTTP://".
		html = '<img src="HTTP://127.0.0.1:9997/probe.png">'
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertNotIn("127.0.0.1:9997", guarded)

	def test_blocks_quoted_css_url_containing_a_space(self):
		html = "<div style=\"background-image:url('http://10.1.2.3/has space.png')\"></div>"
		guarded = pdfgen.guard_pdf_resource_urls(html)
		self.assertNotIn("10.1.2.3", guarded)
