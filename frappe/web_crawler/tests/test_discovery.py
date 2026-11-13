from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.web_crawler import WebCrawler
from frappe.web_crawler.scope import Scope, SkipRules, normalize_url
from frappe.web_crawler.tests.fake_site import FakeSite

XML = "application/xml"


def urlset(*urls: str) -> str:
	locs = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
	return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'


def sitemap_index(*urls: str) -> str:
	locs = "".join(f"<sitemap><loc>{url}</loc></sitemap>" for url in urls)
	return f"<sitemapindex>{locs}</sitemapindex>"


class TestScope(UnitTestCase):
	def test_same_host_under_the_start_path(self):
		scope = Scope("https://www.example.com/docs/")
		self.assertTrue(scope.contains("https://example.com/docs"))
		self.assertTrue(scope.contains("https://www.example.com/docs/install"))
		self.assertFalse(scope.contains("https://example.com/docsearch"))
		self.assertFalse(scope.contains("https://example.com/blog"))
		self.assertFalse(scope.contains("https://other.com/docs/install"))
		self.assertFalse(scope.contains("https://example.com/docs/../admin"))
		self.assertFalse(scope.contains("mailto:docs@example.com"))

	def test_unicode_and_punycode_hosts_are_one_site(self):
		scope = Scope("https://bücher.de/docs")
		self.assertTrue(scope.contains("https://xn--bcher-kva.de/docs/a"))
		self.assertEqual(normalize_url("https://Bücher.de/a"), normalize_url("https://xn--bcher-kva.de/a"))

	def test_normalize_url(self):
		self.assertEqual(normalize_url("HTTPS://Example.com/a/?b=1#c"), "https://example.com/a?b=1")
		self.assertEqual(normalize_url("https://example.com"), "https://example.com/")

	def test_spellings_of_the_same_page_normalize_alike(self):
		for url in (
			"http://www.example.com/docs/",
			"https://example.com/docs/index.html",
			"https://example.com/docs/index.php?utm_source=mail&fbclid=1",
		):
			with self.subTest(url=url):
				self.assertEqual(normalize_url(url), "https://example.com/docs")
		self.assertEqual(
			normalize_url("https://example.com/a?b=2&a=1"), normalize_url("https://example.com/a?a=1&b=2")
		)
		self.assertNotEqual(
			normalize_url("https://example.com/a?id=1"), normalize_url("https://example.com/a?id=2")
		)

	def test_skip_rules(self):
		rules = SkipRules(("/private/", "[unclosed", "/blog/*/draft"))
		for url in (
			"https://example.com/logo.PNG",
			"https://example.com/guide.pdf",
			"javascript:void(0)",
			"https://example.com/private/page",
			"https://example.com/[unclosed",
			"https://example.com/blog/2026/draft-1",
		):
			with self.subTest(url=url):
				self.assertTrue(rules.skips(url))
		self.assertFalse(rules.skips("https://example.com/guide"))
		self.assertFalse(rules.skips("https://example.com/blog/draft"))

	def test_skip_patterns_are_not_regular_expressions(self):
		rules = SkipRules(("(a+)+$",))
		self.assertFalse(rules.skips("https://example.com/" + "a" * 40 + "!"))
		self.assertTrue(rules.skips("https://example.com/(a+)+$"))


class TestDiscovery(IntegrationTestCase):
	def setUp(self):
		self.site = FakeSite(self)

	def find(self, url: str, **options) -> list[str]:
		return WebCrawler(url, **options).find_pages()

	def test_sitemap_under_the_path_wins_over_the_root(self):
		self.site.add("https://example.com/docs/sitemap.xml", urlset("https://example.com/docs/a"), XML)
		self.site.add("https://example.com/sitemap.xml", urlset("https://example.com/docs/b"), XML)
		self.assertEqual(self.find("https://example.com/docs"), ["https://example.com/docs/a"])

	def test_sitemap_named_in_robots_txt(self):
		self.site.add(
			"https://example.com/robots.txt", "Sitemap: https://example.com/hc/map.xml", "text/plain"
		)
		self.site.add("https://example.com/hc/map.xml", urlset("https://example.com/a"), XML)
		self.assertEqual(self.find("https://example.com"), ["https://example.com/a"])

	def test_sitemap_index_is_followed_one_level_on_the_same_site(self):
		self.site.add(
			"https://example.com/sitemap.xml",
			sitemap_index("https://example.com/pages.xml", "https://other.com/pages.xml"),
			XML,
		)
		self.site.add("https://example.com/pages.xml", urlset("https://example.com/a"), XML)
		self.site.add("https://other.com/pages.xml", urlset("https://example.com/b"), XML)
		self.assertEqual(self.find("https://example.com"), ["https://example.com/a"])

	def test_cdata_locations_are_read_in_child_sitemaps_too(self):
		self.site.add("https://example.com/sitemap.xml", sitemap_index("https://example.com/pages.xml"), XML)
		self.site.add(
			"https://example.com/pages.xml",
			"<urlset><url><loc><![CDATA[https://example.com/a?x=1&amp;y=2]]></loc></url></urlset>",
			XML,
		)
		self.assertEqual(self.find("https://example.com"), ["https://example.com/a?x=1&y=2"])

	def test_unsafe_or_unrelated_sitemaps_are_ignored(self):
		for body in (
			'<!DOCTYPE x [<!ENTITY a "a">]>' + urlset("https://example.com/a"),
			"<feed><loc>https://example.com/a</loc></feed>",
			"<html><body>Not a sitemap</body></html>",
		):
			with self.subTest(body=body[:20]):
				self.site.add("https://example.com/sitemap.xml", body, XML)
				self.assertEqual(self.find("https://example.com"), [])

	def test_pasted_sitemap_is_scoped_to_its_folder(self):
		self.site.add(
			"https://example.com/hc/sitemap.xml",
			urlset("https://example.com/hc/a", "https://example.com/blog/b"),
			XML,
		)
		self.assertEqual(self.find("https://example.com/hc/sitemap.xml"), ["https://example.com/hc/a"])

	def test_llms_txt_lists_pages_in_order_and_follows_child_indexes(self):
		self.site.add(
			"https://example.com/docs/llms.txt",
			"# Docs\n- [Setup](/docs/setup.md): how\n* [Install](install)\n- [API](/docs/_llms/api.txt)\n",
			"text/plain",
		)
		self.site.add("https://example.com/docs/_llms/api.txt", "- [Auth](/docs/auth.md)", "text/plain")
		self.assertEqual(
			self.find("https://example.com/docs"),
			[
				"https://example.com/docs/setup.md",
				"https://example.com/docs/install",
				"https://example.com/docs/auth.md",
			],
		)

	def test_an_html_page_at_llms_txt_is_not_an_index(self):
		self.site.page("https://example.com/llms.txt", "<p>An HTML page, not an index</p>")
		self.site.add("https://example.com/sitemap.xml", urlset("https://example.com/a"), XML)
		self.assertEqual(self.find("https://example.com"), ["https://example.com/a"])

	def test_llms_txt_pages_come_before_sitemap_pages_once_each(self):
		self.site.add("https://example.com/llms.txt", "- [B](/b)\n- [A](/a)", "text/plain")
		self.site.add(
			"https://example.com/sitemap.xml",
			urlset("https://example.com/a/", "https://www.example.com/c"),
			XML,
		)
		self.assertEqual(
			self.find("https://example.com"),
			["https://example.com/b", "https://example.com/a", "https://www.example.com/c"],
		)
		self.assertEqual(self.find("https://example.com", index_files=False), [])

	def test_robots_txt_disallow_is_honoured_unless_switched_off(self):
		self.site.add("https://example.com/robots.txt", "User-agent: *\nDisallow: /private", "text/plain")
		self.site.add(
			"https://example.com/sitemap.xml",
			urlset("https://example.com/a", "https://example.com/private/b"),
			XML,
		)
		self.assertEqual(self.find("https://example.com"), ["https://example.com/a"])
		with self.change_settings("Web Crawl Settings", {"respect_robots_txt": 0}):
			self.assertEqual(len(self.find("https://example.com")), 2)

	def test_unreachable_robots_txt_allows_nothing_and_a_missing_one_everything(self):
		self.site.add("https://example.com/sitemap.xml", urlset("https://example.com/a"), XML)
		for status, expected in ((503, []), (429, []), (410, ["https://example.com/a"])):
			with self.subTest(status=status):
				self.site.add("https://example.com/robots.txt", status=status)
				self.assertEqual(self.find("https://example.com"), expected)

	def test_skip_urls_runs_before_the_page_limit(self):
		self.site.add(
			"https://example.com/sitemap.xml",
			urlset("https://example.com/old", "https://example.com/new"),
			XML,
		)
		crawler = WebCrawler(
			"https://example.com",
			max_pages=1,
			skip_urls=lambda urls: [url for url in urls if url.endswith("/old")],
		)
		self.assertEqual(crawler.find_pages(), ["https://example.com/new"])
