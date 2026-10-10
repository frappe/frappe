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


def pdf_with_document_level_js() -> bytes:
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	writer.add_js("app.alert('hello from pdf');")
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def pdf_with_page_level_js() -> bytes:
	from pypdf import PdfWriter
	from pypdf.generic import DictionaryObject, NameObject, TextStringObject

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	action = DictionaryObject(
		{
			NameObject("/S"): NameObject("/JavaScript"),
			NameObject("/JS"): TextStringObject("app.alert('hello from page');"),
		}
	)
	writer.pages[0][NameObject("/AA")] = DictionaryObject({NameObject("/O"): writer._add_object(action)})
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def encrypted_pdf_with_js() -> bytes:
	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=72, height=72)
	writer.add_js("app.alert('hello from encrypted');")
	writer.encrypt("frappe")
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def js_reachable_without_resolving_indirects(content: bytes) -> bool:
	reader = PdfReader(io.BytesIO(content))

	def walk(obj):
		if isinstance(obj, dict):
			for key, value in obj.items():
				if key == "/Parent":
					continue
				if key in ("/JS", "/JavaScript"):
					return True
				if walk(value):
					return True
		elif isinstance(obj, list):
			for item in obj:
				if walk(item):
					return True
		return False

	if walk(reader.trailer.get("/Root", {})):
		return True
	return any(walk(page) for page in reader.pages)


def record_print(**kwargs):
	pass


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

	def test_print_format_margins_are_read_from_html(self):
		from bs4 import BeautifulSoup

		def margins(html):
			styles = pdfgen.get_print_format_styles(BeautifulSoup(html, "html5lib"))
			return {style.name: style.value for style in styles}

		options = margins(self.html)
		self.assertEqual(options["margin-top"], "0")
		self.assertEqual(options["margin-left"], "10mm")
		self.assertEqual(options["margin-right"], "0")

		options = margins(
			"""<style>
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
			<div class="more-info">Hello</div>"""
		)
		self.assertEqual(options["margin-top"], "0")
		self.assertEqual(options["margin-left"], "10mm")
		self.assertEqual(options["margin-bottom"], "20mm")
		self.assertNotIn("margin-right", options)

	def test_pdf_encryption(self):
		password = "qwe"
		pdf = pdfgen.get_pdf(self.html, options={"password": password})
		reader = PdfReader(io.BytesIO(pdf))
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt(password))

	def test_password_with_output_writer_appends_pages(self):
		from pypdf import PdfWriter

		output = pdfgen.get_pdf("<p>first</p>", options={"password": "qwe"}, output=PdfWriter())
		self.assertEqual(len(output.pages), 1)

	def test_repeated_header_marked_hidden_pdf_still_prints(self):
		pdf = pdfgen.get_pdf(
			'<div id="header-html" class="hidden-pdf"><b>REPORT HEADER</b></div><p>report body</p>'
		)
		text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
		self.assertIn("REPORT HEADER", text)
		self.assertIn("report body", text)

	def test_pdf_visibility_classes_apply_to_the_body(self):
		pdf = pdfgen.get_pdf(
			"<style>.visible-pdf { display: none; }</style>"
			'<p class="hidden-pdf">screen only</p><p class="visible-pdf">pdf only</p>'
		)
		text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
		self.assertIn("pdf only", text)
		self.assertNotIn("screen only", text)

	def test_on_print_pdf_hook_runs_for_chrome_prints(self):
		from unittest.mock import patch

		get_hooks = frappe.get_hooks
		calls = []

		def hooks(hook=None, *args, **kwargs):
			if hook == "on_print_pdf":
				return ["frappe.tests.test_pdf.record_print"]
			return get_hooks(hook, *args, **kwargs)

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "print hook"}).insert()

		with (
			patch.object(frappe, "get_hooks", side_effect=hooks),
			patch("frappe.tests.test_pdf.record_print", side_effect=lambda **kw: calls.append(kw)),
			patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"%PDF-"),
		):
			frappe.get_print("ToDo", todo.name, as_pdf=True)

		self.assertEqual(calls, [{"doctype": "ToDo", "name": todo.name, "print_format": None}])

	def test_report_pdf_blocks_external_requests(self):
		from unittest.mock import patch

		from frappe.utils import print_format

		with patch.object(print_format, "get_pdf", return_value=blank_pdf()) as get_report_pdf:
			print_format.report_to_pdf("<table><tr><td>a report</td></tr></table>", orientation="Portrait")

		options = get_report_pdf.call_args.args[1]
		self.assertTrue(options["block-external-requests"])
		self.assertEqual(options["orientation"], "Portrait")

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

	def test_pdf_contains_js_detects_document_level_js(self):
		content = pdf_with_document_level_js()
		self.assertFalse(js_reachable_without_resolving_indirects(content))
		self.assertTrue(pdfgen.pdf_contains_js(content))

	def test_pdf_contains_js_detects_page_level_js(self):
		content = pdf_with_page_level_js()
		self.assertFalse(js_reachable_without_resolving_indirects(content))
		self.assertTrue(pdfgen.pdf_contains_js(content))

	def test_pdf_contains_js_false_for_clean_pdf(self):
		self.assertFalse(pdfgen.pdf_contains_js(blank_pdf()))

	def test_pdf_contains_js_does_not_raise_on_encrypted_pdf(self):
		self.assertFalse(pdfgen.pdf_contains_js(encrypted_pdf_with_js()))


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

	def test_every_print_settings_page_size_is_known(self):
		from frappe.utils.pdf_generator.browser import PageSize

		options = frappe.get_meta("Print Settings").get_field("pdf_page_size").options.split("\n")
		for size in options:
			if size != "Custom":
				self.assertTrue(PageSize.get(size), size)

	def test_landscape_orientation_swaps_paper_size(self):
		for orientation in ("Landscape", "landscape"):
			browser = self.make_browser({"page-size": "A4", "orientation": orientation})
			browser.prepare_options_for_pdf()

			self.assertAlmostEqual(browser.body_page.options["paperWidth"], 11.69, delta=0.05)
			self.assertAlmostEqual(browser.body_page.options["paperHeight"], 8.27, delta=0.05)

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
