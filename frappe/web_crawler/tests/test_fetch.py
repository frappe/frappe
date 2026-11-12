import gzip
import http.server
import threading
import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.safe_exec import BlockedRequest
from frappe.web_crawler import fetch_page
from frappe.web_crawler.fetch import CappedRetry
from frappe.web_crawler.tests.fake_site import NEUTRAL_SETTINGS, FakeSite, allow_domain, block_domain

ARTICLE = """
<head><title>Install | Acme</title><meta name="description" content="How to install">
<meta property="og:image" content="https://example.com/logo.png"></head>
<body><nav><a href="/nav-link">Menu</a></nav>
<article><h1>Install</h1><p>Run <a href="/setup">setup</a>.</p><script>track()</script></article>
<footer>Footer text</footer></body>
"""


class TestFetchPage(IntegrationTestCase):
	def setUp(self):
		self.site = FakeSite(self)

	def test_reads_main_content_title_meta_and_links(self):
		self.site.add("https://example.com/install", ARTICLE)
		page = fetch_page("https://example.com/install")

		self.assertTrue(page.ok)
		self.assertEqual(
			(page.status, page.title, page.description), (200, "Install | Acme", "How to install")
		)
		self.assertEqual(page.meta["og:image"], "https://example.com/logo.png")
		self.assertIn('href="https://example.com/setup"', page.html)
		self.assertNotIn("track()", page.html)
		self.assertNotIn("Footer text", page.text)
		self.assertIn("Footer text", page.raw_html)
		self.assertEqual(page.links["https://example.com/nav-link"], "Menu")
		self.assertIn("Run", page.markdown)

	def test_falls_back_to_body_without_a_main_element(self):
		self.site.page("https://example.com/plain", "<div><p>Plain content</p></div><footer>x</footer>")
		page = fetch_page("https://example.com/plain")
		self.assertEqual(page.text, "Plain content")

	def test_listing_page_keeps_all_its_articles(self):
		self.site.page(
			"https://example.com/blog",
			"<main><article>First post</article><article>Second post</article></main>",
		)
		page = fetch_page("https://example.com/blog")
		self.assertEqual(page.text, "First post\nSecond post")

	def test_title_falls_back_to_the_heading_when_the_title_tag_is_empty(self):
		self.site.page("https://example.com/guide", "<h1>Guide</h1><p>Text</p>")
		self.assertEqual(fetch_page("https://example.com/guide").title, "Guide")

	def test_redirect_to_another_site_is_followed(self):
		self.site.redirect("https://example.com/", "https://example.org/en/")
		self.site.page("https://example.org/en/", "<p>Moved</p>")
		page = fetch_page("https://example.com")
		self.assertEqual((page.error, page.final_url, page.text), (None, "https://example.org/en/", "Moved"))

	def test_meta_charset_is_used_when_the_header_has_none(self):
		body = '<html><head><meta charset="utf-8"></head><body><p>Café</p></body></html>'.encode()
		self.site.add("https://example.com/cafe", body, content_type="text/html")
		self.assertEqual(fetch_page("https://example.com/cafe").text, "Café")

	def test_markdown_page_keeps_its_source_and_front_matter_title(self):
		markdown = "---\ntitle: Setup\n---\n# Heading\n\nOpen **settings**.\n\n---\n\nMore."
		self.site.add("https://example.com/setup.md", markdown, content_type="text/markdown")
		page = fetch_page("https://example.com/setup.md")

		self.assertEqual(page.title, "Setup")
		self.assertIn("<strong>settings</strong>", page.html)
		self.assertTrue(page.markdown.startswith("# Heading"))
		self.assertIn("More.", page.markdown)

	def test_error_codes(self):
		self.site.add("https://example.com/forbidden", status=403)
		self.site.add("https://example.com/broken", status=503)
		self.site.add("https://example.com/unchanged", status=304)
		self.site.add("https://example.com/file", b"%PDF", content_type="application/pdf")
		self.site.page("https://example.com/script-only", "<script>render()</script>")
		expected = {
			"https://example.com/missing": "not_found",
			"https://example.com/forbidden": "blocked",
			"https://example.com/broken": "server_error",
			"https://example.com/unchanged": "failed",
			"https://example.com/file": "not_html",
			"https://example.com/script-only": "empty",
		}
		for url, error in expected.items():
			with self.subTest(url=url):
				page = fetch_page(url)
				self.assertEqual(page.error, error)
				self.assertFalse(page.ok)

	def test_redirect_limit(self):
		for step in range(7):
			self.site.redirect(f"https://example.com/{step}", f"https://example.com/{step + 1}")
		self.assertEqual(fetch_page("https://example.com/0").error, "too_many_redirects")

	def test_size_limit(self):
		with patch("frappe.web_crawler.limits.MEGABYTE", 10):
			self.site.page("https://example.com/big", "<p>" + "x" * 100 + "</p>")
			self.assertEqual(fetch_page("https://example.com/big").error, "too_large")

	def test_gzip_body_is_decoded(self):
		body = gzip.compress(b"<main><p>Compressed</p></main>")
		self.site.add("https://example.com/gzip", body, **{"Content-Encoding": "gzip"})
		self.assertEqual(fetch_page("https://example.com/gzip").text, "Compressed")

	def test_blocked_domains(self):
		self.site.redirect("https://example.com/away", "https://tracker.blocked.com/page")
		block_domain(self, "blocked.com")
		self.assertRaises(BlockedRequest, fetch_page, "https://blocked.com/")
		self.assertRaises(BlockedRequest, fetch_page, "https://www.blocked.com/")
		self.assertEqual(fetch_page("https://example.com/away").error, "blocked")

	def test_allowed_domains(self):
		self.site.redirect("https://example.com/away", "https://example.org/page")
		allow_domain(self, "example.com")
		self.assertRaises(BlockedRequest, fetch_page, "https://example.org/")
		self.assertEqual(fetch_page("https://example.com/away").error, "blocked")

	def test_internal_and_invalid_addresses_raise(self):
		self.assertRaises(BlockedRequest, fetch_page, "http://127.0.0.1/")
		self.assertRaises(frappe.ValidationError, fetch_page, "ftp://example.com/")

	def test_retry_after_wait_is_capped(self):
		response = MagicMock()
		response.headers = {"Retry-After": "3600"}
		self.assertEqual(CappedRetry().get_retry_after(response), 30)


class TestSlowServer(IntegrationTestCase):
	"""A real socket: a body dripped slower than the page timeout must stop at the deadline."""

	def setUp(self):
		server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), DripHandler)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.shutdown)
		self.url = f"http://127.0.0.1:{server.server_address[1]}/drip"
		self.enterContext(patch("frappe.utils.safe_exec.validate_request_url"))
		self.enterContext(patch("frappe.utils.safe_exec.validate_request_address"))
		settings = {**NEUTRAL_SETTINGS, "page_timeout": 1}
		self.enterContext(self.change_settings("Web Crawl Settings", settings))

	def test_slow_body_stops_at_the_deadline(self):
		started = time.monotonic()
		self.assertEqual(fetch_page(self.url).error, "timed_out")
		self.assertLess(time.monotonic() - started, 3)


class DripHandler(http.server.BaseHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.send_header("Content-Type", "text/html")
		self.end_headers()
		try:
			for _ in range(50):
				self.wfile.write(b"<p>x</p>")
				self.wfile.flush()
				time.sleep(0.1)
		except BrokenPipeError:
			pass

	def log_message(self, *args):
		pass
