from unittest.mock import patch

from frappe.tests import IntegrationTestCase
from frappe.web_crawler import WebCrawler
from frappe.web_crawler.limits import CrawlLimits
from frappe.web_crawler.tests.fake_site import FakeSite
from frappe.web_crawler.tests.test_discovery import XML, urlset


def links(*paths: str) -> str:
	return "".join(f'<a href="{path}">{path}</a>' for path in paths)


class TestCrawl(IntegrationTestCase):
	def setUp(self):
		self.site = FakeSite(self)

	def crawl(self, url="https://example.com", **options) -> list:
		return list(WebCrawler(url, sources=("links",), **options).crawl())

	def test_follows_links_breadth_first_within_depth_and_page_limits(self):
		self.site.page("https://example.com/", links("/a", "/b", "https://other.com/x", "/logo.png"))
		self.site.page("https://example.com/a", links("/a/deep"))
		self.site.page("https://example.com/b", "<p>B</p>")
		self.site.page("https://example.com/a/deep", "<p>Deep</p>")

		urls = [page.url for page in self.crawl(max_depth=1)]
		self.assertEqual(urls, ["https://example.com", "https://example.com/a", "https://example.com/b"])
		self.assertEqual(len(self.crawl(max_pages=2)), 2)

	def test_start_page_comes_before_sitemap_seeds(self):
		self.site.page("https://example.com/", "<p>Home</p>")
		self.site.page("https://example.com/listed", "<p>Listed</p>")
		self.site.add("https://example.com/sitemap.xml", urlset("https://example.com/listed"), XML)

		pages = list(WebCrawler("https://example.com", sources=("sitemap", "links")).crawl())
		self.assertEqual([page.url for page in pages], ["https://example.com", "https://example.com/listed"])

	def test_depth_zero_reads_only_the_start_page(self):
		self.site.page("https://example.com/", links("/a"))
		self.site.add("https://example.com/sitemap.xml", urlset("https://example.com/listed"), XML)

		pages = list(WebCrawler("https://example.com", sources=("sitemap", "links"), max_depth=0).crawl())
		self.assertEqual([page.url for page in pages], ["https://example.com"])

	def test_redirect_to_a_page_already_read_costs_no_budget(self):
		self.site.page("https://example.com/", links("/old", "/new", "/other"))
		self.site.redirect("https://example.com/old", "https://example.com/")
		self.site.page("https://example.com/new", "<p>New</p>")
		self.site.page("https://example.com/other", "<p>Other</p>")

		urls = [page.url for page in self.crawl(max_pages=3)]
		self.assertEqual(
			urls, ["https://example.com", "https://example.com/new", "https://example.com/other"]
		)

	def test_pages_are_read_at_the_address_the_link_gives(self):
		self.site.page("https://example.com/", links("/view?id=1", "/view?id=2", "/docs/#intro", "/docs/"))
		for url in (
			"https://example.com/view?id=1",
			"https://example.com/view?id=2",
			"https://example.com/docs/",
		):
			self.site.page(url, f"<p>{url}</p>")

		urls = [page.url for page in self.crawl()]
		self.assertEqual(
			urls[1:],
			["https://example.com/view?id=1", "https://example.com/view?id=2", "https://example.com/docs/"],
		)
		self.assertNotIn("https://example.com/docs", self.site.requested)

	def test_redirect_off_the_site_is_out_of_scope(self):
		self.site.page("https://example.com/", links("/away"))
		self.site.redirect("https://example.com/away", "https://other.com/landing")
		self.site.page("https://other.com/landing", "<p>Elsewhere</p>")

		away = self.crawl()[1]
		self.assertEqual((away.error, away.text), ("off_scope", ""))

	def test_priority_orders_pages_at_the_same_depth(self):
		self.site.page("https://example.com/", links("/blog", "/about"))
		pages = self.crawl(priority=lambda url, anchor_text: "about" in url)
		self.assertEqual(pages[1].url, "https://example.com/about")

	def test_rate_limit_stops_the_crawl(self):
		self.site.page("https://example.com/", links("/a", "/b"))
		self.site.add("https://example.com/a", status=429, **{"Retry-After": "1"})
		crawler = WebCrawler("https://example.com", sources=("links",))

		pages = list(crawler.crawl())
		self.assertEqual([page.status for page in pages], [200, 429])
		self.assertEqual(crawler.stopped_reason, "rate_limited")
		self.assertEqual(self.site.requested.count("https://example.com/a"), 3)

	def test_crawl_stops_at_the_time_limit(self):
		self.site.page("https://example.com/", links("/a", "/b"))
		self.site.page("https://example.com/a", "<p>A</p>")
		crawler = WebCrawler("https://example.com", sources=("links",))
		pages = crawler.crawl()

		self.assertEqual(next(pages).url, "https://example.com")
		crawler.fetcher.deadline = 0.1
		self.assertEqual(list(pages), [])
		self.assertEqual(crawler.stopped_reason, "time_limit")

	def test_waits_between_requests_for_the_longer_of_setting_and_crawl_delay(self):
		self.site.add("https://example.com/robots.txt", "User-agent: *\nCrawl-delay: 2", "text/plain")
		self.site.page("https://example.com/", links("/a"))
		with patch("frappe.web_crawler.crawler.time.sleep") as sleep:
			self.crawl()
		self.assertAlmostEqual(sleep.call_args.args[0], 2, delta=0.1)


class TestCrawlLimits(IntegrationTestCase):
	def test_arguments_only_lower_the_settings(self):
		with self.change_settings("Web Crawler Settings", {"max_pages": 20, "max_depth": 2}):
			self.assertEqual(CrawlLimits.from_settings(5, 9).max_pages, 5)
			self.assertEqual(CrawlLimits.from_settings(50, 9).max_pages, 20)
			self.assertEqual(CrawlLimits.from_settings(None, 9).max_depth, 2)

	def test_job_outlives_the_crawl_time(self):
		with self.change_settings("Web Crawler Settings", {"max_crawl_time": 10}):
			limits = CrawlLimits.from_settings()
		self.assertEqual(limits.max_crawl_time, 600)
		self.assertGreater(limits.job_timeout(), 600 + 3 * 30)

	def test_wait_is_capped(self):
		with self.change_settings("Web Crawler Settings", {"request_delay": 1}):
			limits = CrawlLimits.from_settings()
			self.assertEqual(limits.wait_seconds(None), 1)
			self.assertEqual(limits.wait_seconds(5), 5)
			self.assertEqual(limits.wait_seconds(300), 30)
