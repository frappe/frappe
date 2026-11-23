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


def record_print(**kwargs):
	pass


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

<<<<<<< HEAD
=======
	def test_internal_link_lands_on_its_target_with_footer(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_pdf(
			'<a href="#totals">See totals</a>'
			+ "<p>row</p>" * 80
			+ '<p id="totals">Totals</p><div id="footer-html"><p style="height: 150px">BOTTOM</p></div>'
		)
		reader = PdfReader(io.BytesIO(pdf))
		page, _, _, top, _ = reader.pages[0]["/Annots"][0].get_object()["/Dest"]
		baselines = []

		def record_baseline(text, cm, tm, *_):
			if text.strip() == "Totals":
				baselines.append(tm[4] * cm[1] + tm[5] * cm[3] + cm[5])

		reader.pages[reader.get_page_number(page.get_object())].extract_text(visitor_text=record_baseline)
		self.assertEqual(len(baselines), 1)
		self.assertGreater(top, baselines[0])
		self.assertLess(top, baselines[0] + 72)

	def test_header_and_footer_keep_the_document_title(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_pdf(
			"<title>Sales Invoice: SINV-0001</title>"
			'<div id="header-html"><b>TOP</b></div><p>body text</p><div id="footer-html"><b>BOTTOM</b></div>'
		)
		self.assertEqual(PdfReader(io.BytesIO(pdf)).metadata.title, "Sales Invoice: SINV-0001")

	def test_footer_is_measured_at_the_width_it_prints(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		block = '<span style="display: inline-block; width: 380px; height: 40px"></span>'
		footer = (
			f'<div id="footer-html">{block}{block}'
			'<p>Page <span class="page"></span> of <span class="topage"></span></p></div>'
		)
		pages = PdfReader(io.BytesIO(pdfgen.get_pdf("<p>row</p>" * 120 + footer))).pages
		self.assertGreater(len(pages), 1)
		for number, page in enumerate(pages, start=1):
			self.assertIn(f"Page {number} of {len(pages)}", page.extract_text())

	def test_footer_visible_last_page_prints_on_last_page_only(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		html = (
			"<p>row</p>" * 120 + '<div id="footer-html"><p class="visible-last-page">Grand Total</p>'
			'<p>Page <span class="page"></span> of <span class="topage"></span></p></div>'
		)
		for pdf_generator in ("chrome", "PlutoPrint"):
			with self.subTest(pdf_generator=pdf_generator):
				pdf = pdfgen.get_pdf(html, pdf_generator=pdf_generator)
				texts = [page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages]
				self.assertGreater(len(texts), 1)
				self.assertNotIn("Grand Total", "".join(texts[:-1]))
				self.assertIn("Grand Total", texts[-1])

	def test_pdf_renders_while_another_render_has_a_tab_open(self):
		from frappe.utils.chromium import CDPSocketClient, ChromiumManager, Page
		from frappe.utils.pdf import get_host_url

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		generator, token = ChromiumManager.acquire()
		self.addCleanup(generator.release, token)
		if not generator._devtools_url:
			generator._set_devtools_url()
		session = CDPSocketClient(generator._devtools_url)
		session.connect()
		self.addCleanup(session.disconnect)
		context, _error = session.send("Target.createBrowserContext", {"disposeOnDetach": True})
		page = Page(session, context["browserContextId"], "body")
		page.set_tab_url(get_host_url())
		page.wait_for_navigate()

		pdf = pdfgen.get_pdf("<p>body text</p>")
		self.assertIn("body text", PdfReader(io.BytesIO(pdf)).pages[0].extract_text())

	def test_two_pdfs_started_together_both_render(self):
		import threading

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		site, sites_path = frappe.local.site, frappe.local.sites_path
		pdfs = []
		both_ready = threading.Barrier(2)

		def render():
			try:
				frappe.init(site, sites_path=sites_path)
				frappe.connect()
				frappe.set_user("test@example.com")
				both_ready.wait()
				pdfs.append(pdfgen.get_pdf("<p>body text</p>"))
			finally:
				frappe.destroy()

		renders = [threading.Thread(target=render, daemon=True) for _ in range(2)]
		for thread in renders:
			thread.start()
		for thread in renders:
			thread.join(timeout=60)
		self.assertEqual(len(pdfs), 2)

	def test_pages_merged_with_header_and_footer_are_compressed(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_pdf(
			'<div id="header-html"><b>TOP</b></div><p>body text</p><div id="footer-html"><b>BOTTOM</b></div>'
		)
		contents = PdfReader(io.BytesIO(pdf)).pages[0]["/Contents"]
		self.assertEqual(contents.get("/Filter"), "/FlateDecode")

	def test_header_is_measured_after_its_image_loads(self):
		import threading
		import time
		from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
		from unittest.mock import patch

		class SlowImageHandler(BaseHTTPRequestHandler):
			def do_GET(self):
				time.sleep(0.5)
				self.send_response(200)
				self.send_header("Content-Type", "image/svg+xml")
				self.end_headers()
				self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="900"/>')

		server = ThreadingHTTPServer(("127.0.0.1", 0), SlowImageHandler)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		with patch("frappe.utils.chromium.page.allows_internal_print_urls", return_value=True):
			pdf = pdfgen.get_pdf(
				f'<div id="header-html"><img src="http://127.0.0.1:{server.server_port}"></div>'
				+ "<p>row</p>" * 10
			)
		self.assertGreater(len(PdfReader(io.BytesIO(pdf)).pages), 1)

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

>>>>>>> 9026635 (test(print): pdf resources load through the safe request session)
	def test_bulk_pdf_bookmarks_each_document(self):
		from frappe.utils.print_format import _download_multi_pdf

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		names = [
			frappe.get_doc({"doctype": "ToDo", "description": description}).insert().name
			for description in ("Call Northwind Traders", "Follow up with Litware")
		]

		_download_multi_pdf("ToDo", frappe.as_json(names))

		reader = PdfReader(io.BytesIO(frappe.local.response.filecontent))
		self.assertEqual(
			[(item.title, reader.get_destination_page_number(item)) for item in reader.outline],
			[(names[0], 0), (names[1], 1)],
		)

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

	def test_pdf_renders_while_another_render_has_a_tab_open(self):
		from frappe.utils.pdf import get_host_url
		from frappe.utils.pdf_generator.cdp_connection import CDPSocketClient
		from frappe.utils.pdf_generator.chrome_pdf_generator import ChromePDFGenerator
		from frappe.utils.pdf_generator.page import Page

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		generator = ChromePDFGenerator()
		if not generator._devtools_url:
			generator._set_devtools_url()
		self.addCleanup(generator._close_browser)
		generator.add_browser("other-render")
		self.addCleanup(generator.remove_browser, "other-render")
		session = CDPSocketClient(generator._devtools_url)
		session.connect()
		self.addCleanup(session.disconnect)
		context, _error = session.send("Target.createBrowserContext", {"disposeOnDetach": True})
		page = Page(session, context["browserContextId"], "body")
		page.set_tab_url(get_host_url())
		page.wait_for_navigate()

		pdf = pdfgen.get_chrome_pdf(None, "<p>body text</p>", {}, None, pdf_generator="chrome")
		self.assertIn("body text", PdfReader(io.BytesIO(pdf)).pages[0].extract_text())

	def test_pages_merged_with_header_and_footer_are_compressed(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		pdf = pdfgen.get_chrome_pdf(
			None,
			'<div id="header-html"><b>TOP</b></div><p>body text</p><div id="footer-html"><b>BOTTOM</b></div>',
			{},
			None,
			pdf_generator="chrome",
		)
		contents = PdfReader(io.BytesIO(pdf)).pages[0]["/Contents"]
		self.assertEqual(contents.get("/Filter"), "/FlateDecode")

	def test_footer_is_measured_at_the_width_it_prints(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		block = '<span style="display: inline-block; width: 380px; height: 40px"></span>'
		footer = (
			f'<div id="footer-html">{block}{block}'
			'<p>Page <span class="page"></span> of <span class="topage"></span></p></div>'
		)
		pdf = pdfgen.get_chrome_pdf(None, "<p>row</p>" * 120 + footer, {}, None, pdf_generator="chrome")
		pages = PdfReader(io.BytesIO(pdf)).pages
		self.assertGreater(len(pages), 1)
		for number, page in enumerate(pages, start=1):
			self.assertIn(f"Page {number} of {len(pages)}", page.extract_text())

	def _builder_format(self):
		import json

		layout = {
			"sections": [
				{
					"label": "Details",
					"columns": [
						{
							"label": "",
							"fields": [
								{"fieldtype": "Data", "fieldname": "description", "label": "Description"}
							],
						}
					],
				}
			],
			"header": {"columns": [{"label": "", "fields": []}]},
			"footer": {"columns": [{"label": "", "fields": []}]},
		}
		print_format = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test Print Hook {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"standard": "No",
				"format_data": json.dumps(layout),
			}
		).insert(ignore_permissions=True)
		self.addCleanup(print_format.delete, ignore_permissions=True)
		return print_format

	def _assert_print_hook_and_access_log(self, print_with):
		from unittest.mock import patch

		get_hooks = frappe.get_hooks
		calls = []

		def hooks(hook=None, *args, **kwargs):
			if hook == "on_print_pdf":
				return ["frappe.tests.test_pdf.record_print"]
			return get_hooks(hook, *args, **kwargs)

		print_format = self._builder_format()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "print hook"}).insert()

		with (
			patch.object(frappe, "get_hooks", side_effect=hooks),
			patch("frappe.tests.test_pdf.record_print", side_effect=lambda **kw: calls.append(kw)),
			patch(
				"frappe.utils.print_format_generator.PrintFormatGenerator.render_pdf",
				return_value=blank_pdf(),
			),
		):
			print_with(todo, print_format)

		self.assertEqual(calls, [{"doctype": "ToDo", "name": todo.name, "print_format": print_format.name}])
		self.assertTrue(
			frappe.db.exists(
				"Access Log", {"reference_document": todo.name, "page": f"Print Format: {print_format.name}"}
			)
		)

	def test_emailed_builder_print_runs_the_hook_and_access_log(self):
		self._assert_print_hook_and_access_log(
			lambda todo, print_format: frappe.attach_print("ToDo", todo.name, print_format=print_format.name)
		)

	def test_bulk_builder_print_runs_the_hook_and_access_log(self):
		from frappe.utils.print_format import _download_multi_pdf

		self._assert_print_hook_and_access_log(
			lambda todo, print_format: _download_multi_pdf(
				"ToDo", frappe.as_json([todo.name]), format=print_format.name
			)
		)

	def test_bulk_pdf_lists_the_documents_it_could_not_print(self):
		from unittest.mock import ANY, patch

		from frappe.utils.print_format import _download_multi_pdf

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Call Northwind Traders"}).insert()
		deleted = frappe.get_doc({"doctype": "ToDo", "description": "Follow up with Litware"}).insert()
		deleted.delete()

		with patch.object(frappe, "publish_realtime") as publish_realtime:
			_download_multi_pdf("ToDo", frappe.as_json([todo.name, deleted.name]))

		publish_realtime.assert_called_with(event="msgprint", message=ANY)
		self.assertIn(deleted.name, publish_realtime.call_args.kwargs["message"].message[0])

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

	def test_on_print_pdf_hook_runs_for_builder_downloads(self):
		from unittest.mock import patch

		from frappe.utils.print_format_generator import download_pdf

		get_hooks = frappe.get_hooks
		calls = []

		def hooks(hook=None, *args, **kwargs):
			if hook == "on_print_pdf":
				return ["frappe.tests.test_pdf.record_print"]
			return get_hooks(hook, *args, **kwargs)

		print_format = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "_Test Builder Format",
				"doc_type": "ToDo",
				"standard": "No",
				"print_format_builder_beta": 1,
			}
		).insert()
		self.addCleanup(print_format.delete)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "print hook"}).insert()

		with (
			patch.object(frappe, "get_hooks", side_effect=hooks),
			patch("frappe.tests.test_pdf.record_print", side_effect=lambda **kw: calls.append(kw)),
		):
			download_pdf("ToDo", todo.name, print_format=print_format.name)

		self.assertEqual(calls, [{"doctype": "ToDo", "name": todo.name, "print_format": print_format.name}])

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

	def test_landscape_orientation_swaps_paper_size(self):
		from types import SimpleNamespace

		from bs4 import BeautifulSoup

		from frappe.utils.pdf_generator.browser import Browser

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		for orientation in ("Landscape", "landscape"):
			browser = Browser.__new__(Browser)
			browser.is_print_designer = False
			browser.print_format = None
			browser.options = {"page-size": "A4", "orientation": orientation}
			browser.soup = BeautifulSoup("", "html5lib")
			browser.body_page = SimpleNamespace(options={})
			browser.header_page = browser.footer_page = None
			browser.prepare_options_for_pdf()

			self.assertAlmostEqual(browser.body_page.options["paperWidth"], 11.69, delta=0.05)
			self.assertAlmostEqual(browser.body_page.options["paperHeight"], 8.27, delta=0.05)

	def test_b5_page_size_is_portrait(self):
		from types import SimpleNamespace

		from bs4 import BeautifulSoup

		from frappe.utils.pdf_generator.browser import Browser

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		browser = Browser.__new__(Browser)
		browser.is_print_designer = False
		browser.print_format = None
		browser.options = {"page-size": "B5"}
		browser.soup = BeautifulSoup("", "html5lib")
		browser.body_page = SimpleNamespace(options={})
		browser.header_page = browser.footer_page = None
		browser.prepare_options_for_pdf()

		self.assertAlmostEqual(browser.body_page.options["paperWidth"], 6.93, delta=0.05)
		self.assertAlmostEqual(browser.body_page.options["paperHeight"], 9.84, delta=0.05)
