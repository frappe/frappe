# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest
from io import BytesIO

from PIL import Image

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.preview import get_preview_from_url


def is_chromium_available() -> bool:
	"""True only if Chromium is already on disk.

	Avoids triggering a ~150MB download during a normal test run — matching the
	suite norm where Chrome-backed rendering is not exercised in CI.
	"""
	import shutil

	from frappe.utils.print_utils import EXECUTABLE_PATHS

	configured = frappe.get_common_site_config().get("chromium_path", "")
	if configured and shutil.which(configured):
		return True

	import platform
	from pathlib import Path

	executable_name = EXECUTABLE_PATHS.get(platform.system().lower())
	if not executable_name:
		return False
	exec_path = Path(frappe.utils.get_bench_path()).joinpath("chromium", *executable_name)
	return exec_path.exists()


@unittest.skipUnless(is_chromium_available(), "Chromium is not installed")
class TestPreview(IntegrationTestCase):
	"""Native preview-image generation via the headless-Chromium CDP stack.

	These hit real Chromium, so they only run when it is already installed.
	"""

	HTML = (
		"<html><body style='margin:0'>"
		"<div style='width:100%;height:200px;background:#16a34a'>preview</div>"
		"</body></html>"
	)

	def assert_image(self, data: bytes, expected_format: str):
		self.assertTrue(data, "no image bytes returned")
		img = Image.open(BytesIO(data))
		self.assertEqual(img.format, expected_format)
		# default viewport mirrors the old Playwright generator
		self.assertEqual(img.size, (1280, 720))

	def test_get_preview_from_html_jpeg(self):
		from frappe.utils.preview import get_preview_from_html

		self.assert_image(get_preview_from_html(self.HTML, format="jpg"), "JPEG")

	def test_get_preview_from_html_webp(self):
		from frappe.utils.preview import get_preview_from_html

		self.assert_image(get_preview_from_html(self.HTML, format="webp"), "WEBP")

	def test_get_preview_from_url_renders_content(self):
		"""URL navigation must load real content, not the empty navigation stub
		used by the HTML flow."""
		from frappe.utils.preview import get_preview_from_url

		data_url = (
			"data:text/html,<html><body style='margin:0;background:%23dc2626'>"
			"<h1 style='color:white'>nav</h1></body></html>"
		)
		data = get_preview_from_url(data_url, format="jpg")
		self.assert_image(data, "JPEG")
		# A blank navigation stub renders as near-uniform white (a handful of
		# colors); a real page render has many. Asserting on colour variety keeps
		# this robust against jpeg compression noise.
		colors = Image.open(BytesIO(data)).convert("RGB").getcolors(maxcolors=1 << 20)
		self.assertGreater(len(colors or []), 100)

	def test_get_preview_from_url_full_page(self):
		from frappe.utils.preview import get_preview_from_url

		data_url = "data:text/html,<body style='margin:0'><div style='height:2000px'></div></body>"
		data = get_preview_from_url(data_url, width=800, height=600, full_page=True)
		self.assertEqual(Image.open(BytesIO(data)).size, (800, 2000))

		data = get_preview_from_url(data_url, width=800, height=600)
		self.assertEqual(Image.open(BytesIO(data)).size, (800, 600))

	def test_get_preview_from_url_waits_until_ready(self):
		from frappe.utils.preview import get_preview_from_url

		data_url = (
			"data:text/html,<body style='margin:0'><script>setTimeout(() => {"
			"const div = document.createElement('div'); div.id = 'late';"
			"div.style.height = '3000px'; document.body.appendChild(div);"
			"}, 1500)</script></body>"
		)
		data = get_preview_from_url(
			data_url, full_page=True, wait_until="document.getElementById('late')", timeout=10
		)
		self.assertEqual(Image.open(BytesIO(data)).size, (1280, 3000))

	def test_get_preview_from_url_wait_until_times_out(self):
		import time

		from frappe.utils.preview import get_preview_from_url

		start = time.monotonic()
		with self.assertRaises(TimeoutError):
			get_preview_from_url("data:text/html,<body></body>", wait_until="window.never", timeout=2)
		self.assertLess(time.monotonic() - start, 10)

	def test_get_preview_from_url_wait_until_syntax_error(self):
		from frappe.utils.preview import get_preview_from_url

		with self.assertRaises(SyntaxError):
			get_preview_from_url("data:text/html,<body></body>", wait_until="window.ready;", timeout=30)

	def test_get_preview_from_url_full_page_height_cap(self):
		from frappe.utils.preview import MAX_FULL_PAGE_HEIGHT, get_preview_from_url

		data_url = "data:text/html,<body style='margin:0'><div style='height:20000px'></div></body>"
		data = get_preview_from_url(data_url, format="webp", width=200, full_page=True)
		self.assertEqual(Image.open(BytesIO(data)).size, (200, MAX_FULL_PAGE_HEIGHT))

	def test_get_preview_from_url_sends_headers_only_to_its_origin(self):
		import threading
		from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

		from frappe.utils.preview import get_preview_from_url

		received = []

		class Handler(BaseHTTPRequestHandler):
			def do_GET(self):
				received.append((self.server.server_port, self.path, self.headers.get("X-Preview-Key")))
				body = b""
				if self.path == "/page":
					body = f"<img src='http://127.0.0.1:{other.server_port}/pixel'>".encode()
				self.send_response(200)
				self.send_header("Content-Type", "text/html")
				self.send_header("Content-Length", str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def log_message(self, *args):
				pass

		own, other = (
			ThreadingHTTPServer(("127.0.0.1", 0), Handler),
			ThreadingHTTPServer(("127.0.0.1", 0), Handler),
		)
		for server in (own, other):
			threading.Thread(target=server.serve_forever, daemon=True).start()
			self.addCleanup(server.server_close)
			self.addCleanup(server.shutdown)

		get_preview_from_url(
			f"http://127.0.0.1:{own.server_port}/page",
			headers={"X-Preview-Key": "secret"},
			wait_until="document.images[0].complete",
			timeout=10,
		)
		self.assertIn((own.server_port, "/page", "secret"), received)
		self.assertIn((other.server_port, "/pixel", None), received)

	def test_get_preview_from_url_invalid_header_raises(self):
		from frappe.utils.preview import get_preview_from_url

		with self.assertRaises(ValueError):
			get_preview_from_url("http://127.0.0.1:9/", headers={"X-Key": "a\nb"})

	def test_get_preview_from_url_headers_skip_frames_of_a_url_without_origin(self):
		received = []
		other = self.start_server(received)

		get_preview_from_url(
			f"data:text/html,<iframe src='http://127.0.0.1:{other.server_port}/frame'></iframe>",
			headers={"X-Preview-Key": "secret"},
		)
		self.assertIn((other.server_port, "/frame", None), received)

	def test_get_preview_from_url_wait_until_does_not_wait_for_network_idle(self):
		import time

		received = []
		server = self.start_server(received)

		start = time.monotonic()
		data = get_preview_from_url(
			f"http://127.0.0.1:{server.server_port}/hold-page", wait_until="true", timeout=10
		)
		self.assertTrue(data)
		self.assertLess(time.monotonic() - start, 5)

	def start_server(self, received):
		import threading
		import time
		from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

		class Handler(BaseHTTPRequestHandler):
			def do_GET(self):
				received.append((self.server.server_port, self.path, self.headers.get("X-Preview-Key")))
				if self.path == "/hold":
					time.sleep(30)
					return
				body = (
					b"<img src='/hold'><script>fetch('/hold')</script>" if self.path == "/hold-page" else b""
				)
				self.send_response(200)
				self.send_header("Content-Type", "text/html")
				self.send_header("Content-Length", str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def log_message(self, *args):
				pass

		server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		server.daemon_threads = True
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		return server

	def test_get_preview_from_url_timeout_bounds_a_stalled_wait_until(self):
		import time

		from frappe.utils.preview import get_preview_from_url

		start = time.monotonic()
		with self.assertRaises(TimeoutError):
			get_preview_from_url(
				"data:text/html,<body></body>", wait_until="(() => { while (true); })()", timeout=2
			)
		self.assertLess(time.monotonic() - start, 10)

	def test_get_preview_from_url_timeout_bounds_a_slow_response(self):
		import threading
		import time
		from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

		from frappe.utils.preview import get_preview_from_url

		class Handler(BaseHTTPRequestHandler):
			def do_GET(self):
				time.sleep(20)

			def log_message(self, *args):
				pass

		server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		server.daemon_threads = True
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)

		start = time.monotonic()
		with self.assertRaises(TimeoutError):
			get_preview_from_url(f"http://127.0.0.1:{server.server_port}/", wait_until="true", timeout=2)
		self.assertLess(time.monotonic() - start, 10)


class TestPreviewValidation(IntegrationTestCase):
	"""Format validation raises before Chromium is touched, so it runs everywhere."""

	def test_wait_until_needs_a_positive_timeout(self):
		from frappe.utils.preview import get_preview_from_url

		with self.assertRaises(ValueError):
			get_preview_from_url("data:text/html,<body></body>", wait_until="true", timeout=0)

	def test_invalid_format_raises(self):
		from frappe.utils.preview import get_preview_from_html

		with self.assertRaises(frappe.ValidationError):
			get_preview_from_html("<html></html>", format="png")
