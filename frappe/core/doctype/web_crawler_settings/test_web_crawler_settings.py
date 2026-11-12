# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.web_crawler.limits import CrawlLimits
from frappe.web_crawler.tests.fake_site import allow_domain, block_domain


class IntegrationTestWebCrawlerSettings(IntegrationTestCase):
	def test_limits_must_be_positive(self):
		settings = frappe.get_doc("Web Crawler Settings")
		settings.page_timeout = 0
		self.assertRaises(frappe.ValidationError, settings.save)

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
