# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.web_crawler.limits import CrawlLimits
from frappe.web_crawler.tests.fake_site import allow_domain, block_domain
from frappe.website.doctype.web_crawl_settings.web_crawl_settings import warn_if_crawl_may_stop_early


class IntegrationTestWebCrawlSettings(IntegrationTestCase):
	def test_limits_must_be_positive(self):
		settings = frappe.get_doc("Web Crawl Settings")
		settings.page_timeout = 0
		self.assertRaises(frappe.ValidationError, settings.save)

	def test_warns_about_many_concurrent_requests(self):
		settings = frappe.get_doc("Web Crawl Settings")
		frappe.clear_messages()
		settings.concurrent_requests = 5
		settings.save()
		self.assertNotIn("Many concurrent requests", str(frappe.get_message_log()))
		settings.concurrent_requests = 6
		settings.save()
		self.assertIn("Many concurrent requests", str(frappe.get_message_log()))

	def test_warns_when_a_full_crawl_may_outlast_the_crawl_time(self):
		settings = {"max_pages": 1000, "request_delay": 1, "max_crawl_time": 30, "concurrent_requests": 1}
		with self.change_settings("Web Crawl Settings", settings):
			frappe.clear_messages()
			self.assertEqual(CrawlLimits.from_settings(300).estimated_crawl_time(), 600)
			warn_if_crawl_may_stop_early(CrawlLimits.from_settings(300))
			self.assertEqual(frappe.get_message_log(), [])
			warn_if_crawl_may_stop_early(CrawlLimits.from_settings())
		self.assertIn("Crawl may stop early", str(frappe.get_message_log()))

	def test_blocked_domain_covers_its_subdomains(self):
		block_domain(self, "Blocked.com")
		limits = CrawlLimits.from_settings()
		self.assertTrue(limits.is_blocked("https://blocked.com/"))
		self.assertTrue(limits.is_blocked("https://docs.blocked.com/page"))
		self.assertFalse(limits.is_blocked("https://notblocked.com/"))

	def test_allowed_domains_block_every_other_domain(self):
		allow_domain(self, "example.com")
		block_domain(self, "private.example.com")
		limits = CrawlLimits.from_settings()
		self.assertFalse(limits.is_blocked("https://example.com/"))
		self.assertFalse(limits.is_blocked("https://docs.example.com/page"))
		self.assertTrue(limits.is_blocked("https://private.example.com/"))
		self.assertTrue(limits.is_blocked("https://example.org/"))
