# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.core.doctype.web_crawl.web_crawl import WebCrawl
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime
from frappe.web_crawler import CrawledPage, WebCrawler
from frappe.web_crawler.tests.fake_site import FakeSite

OWNER = "web-crawl-owner@example.com"
READER = "web-crawl-reader@example.com"
STRANGER = "web-crawl-stranger@example.com"
SEEN_PAGES = []


def record_page(page: CrawledPage, web_crawl: WebCrawl):
	if "broken" in page.url:
		raise ValueError("on_page failed")
	SEEN_PAGES.append((page.url, web_crawl.name))


class IntegrationTestWebCrawl(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for user in (OWNER, READER, STRANGER):
			create_user(user, "Blogger")

	def setUp(self):
		SEEN_PAGES.clear()
		self.site = FakeSite(self)
		self.site.page("https://example.com/", '<a href="/a">A</a><a href="/broken">Broken</a><p>Home</p>')
		self.site.page("https://example.com/a", "<p>Page A</p>")
		self.site.page("https://example.com/broken", "<p>Broken</p>")
		self.enterContext(patch("frappe.enqueue_task", return_value=frappe._dict(name="task-1")))
		self.enterContext(patch.object(frappe.db, "commit"))

	def start_crawl(self, user=OWNER, **caller) -> WebCrawl:
		with self.set_user(user):
			crawler = WebCrawler("https://example.com", sources=("links",))
			return crawler.enqueue(on_page=f"{__name__}.record_page", **caller)

	def test_run_stores_pages_and_summary_and_survives_a_failing_on_page(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			summary = web_crawl.run()

		self.assertEqual(
			summary,
			{
				"pages": 3,
				"ok": 2,
				"failed": 1,
				"errors": {"https://example.com/broken": "failed"},
				"stopped": None,
			},
		)
		self.assertEqual(len(SEEN_PAGES), 2)
		stored = frappe.get_all("Web Crawl Page", {"web_crawl": web_crawl.name}, pluck="url")
		self.assertCountEqual(stored, ["https://example.com/", "https://example.com/a"])
		web_crawl.reload()
		self.assertEqual(
			(web_crawl.status, web_crawl.pages_crawled, web_crawl.pages_failed), ("Completed", 3, 1)
		)

	def test_enqueue_returns_the_crawl_already_running(self):
		first = self.start_crawl()
		self.assertEqual(first.background_task, "task-1")
		self.assertEqual(self.start_crawl().name, first.name)

	def test_start_refuses_a_crawl_that_has_started(self):
		web_crawl = self.start_crawl()
		self.assertRaises(frappe.ValidationError, web_crawl.start)

	def test_invalid_url_is_rejected(self):
		web_crawl = frappe.get_doc({"doctype": "Web Crawl", "url": "http://127.0.0.1/"})
		self.assertRaises(frappe.ValidationError, web_crawl.insert)

	def test_owner_and_readers_of_the_reference_document_can_read(self):
		web_crawl = self.start_crawl(reference_doctype="User", reference_name=READER)
		with self.set_user(OWNER):
			web_crawl.run()
		page_name = frappe.get_all("Web Crawl Page", {"web_crawl": web_crawl.name}, pluck="name")[0]

		for user, can_read in ((OWNER, True), (READER, True), (STRANGER, False)):
			with self.subTest(user=user), self.set_user(user):
				self.assertEqual(bool(frappe.has_permission("Web Crawl", "read", web_crawl.name)), can_read)
				self.assertEqual(bool(frappe.has_permission("Web Crawl Page", "read", page_name)), can_read)
				self.assertFalse(frappe.has_permission("Web Crawl", "write", web_crawl.name))

	def test_lists_show_only_own_crawls(self):
		web_crawl = self.start_crawl()
		for user, expected in ((OWNER, [web_crawl.name]), (STRANGER, [])):
			with self.subTest(user=user), self.set_user(user):
				self.assertEqual(frappe.get_list("Web Crawl", pluck="name"), expected)

	def test_only_the_owner_can_stop(self):
		self.enterContext(patch("rq.job.Job.fetch"))
		web_crawl = self.start_crawl()
		frappe.get_doc(
			{
				"doctype": "Background Task",
				"task_id": "task-1",
				"task_name": "Crawl",
				"status": "Queued",
				"user": OWNER,
				"method": "x",
			}
		).insert(ignore_permissions=True)
		with self.set_user(STRANGER):
			self.assertRaises(frappe.PermissionError, web_crawl.stop)
		with self.set_user(OWNER):
			web_crawl.stop()
		self.assertEqual(web_crawl.status, "Cancelled")

	def test_old_crawls_are_cleared_with_their_pages(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			web_crawl.run()
		web_crawl.db_set("creation", add_days(now_datetime(), -31))

		WebCrawl.clear_old_logs(days=30)
		self.assertFalse(frappe.db.exists("Web Crawl", web_crawl.name))
		self.assertFalse(frappe.db.exists("Web Crawl Page", {"web_crawl": web_crawl.name}))
