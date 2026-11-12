# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime
from frappe.web_crawler import CrawledPage, KeywordPriority, WebCrawler
from frappe.web_crawler.tests.fake_site import FakeSite, add_setting_row
from frappe.website.doctype.web_crawl.web_crawl import WebCrawl

OWNER = "web-crawl-owner@example.com"
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
		for user in (OWNER, STRANGER):
			create_user(user, "Blogger")

	def setUp(self):
		SEEN_PAGES.clear()
		frappe.db.savepoint("web_crawl_test")
		self.addCleanup(frappe.db.rollback, save_point="web_crawl_test")
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

	def insert_background_task(self):
		frappe.get_doc(
			{
				"doctype": "Background Task",
				"task_id": "task-1",
				"task_name": "Crawl",
				"status": "Queued",
				"user": OWNER,
				"method": "x",
				"ref_doctype": "Web Crawl",
				"ref_docname": frappe.db.get_value("Web Crawl", {"background_task": "task-1"}),
			}
		).insert(ignore_permissions=True)

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
		stored = frappe.get_all("Web Crawl Result", {"web_crawl": web_crawl.name}, pluck="url")
		self.assertCountEqual(stored, ["https://example.com", "https://example.com/a"])
		web_crawl.reload()
		self.assertEqual(
			(web_crawl.status, web_crawl.pages_crawled, web_crawl.pages_failed), ("Completed", 3, 1)
		)

	def test_long_urls_and_titles_are_stored(self):
		long_path = "/" + "a" * 300
		self.site.page("https://example.com/", f'<a href="{long_path}">Long</a>')
		self.site.page(f"https://example.com{long_path}", "<p>Long</p>", title="t" * 300)
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			self.assertEqual(web_crawl.run()["failed"], 0)

	def test_enqueue_returns_the_crawl_already_running(self):
		first = self.start_crawl()
		self.assertEqual(first.background_task, "task-1")
		self.assertEqual(self.start_crawl().name, first.name)

	def test_enqueue_starts_a_new_crawl_for_another_caller_or_user(self):
		first = self.start_crawl(reference_doctype="User", reference_name=OWNER)
		for user, reference_name in ((OWNER, STRANGER), (STRANGER, OWNER)):
			with self.subTest(user=user, reference_name=reference_name):
				other = self.start_crawl(user, reference_doctype="User", reference_name=reference_name)
				self.assertNotEqual(other.name, first.name)

	def test_enqueue_starts_a_new_crawl_for_other_sources(self):
		first = self.start_crawl()
		with self.set_user(OWNER):
			crawler = WebCrawler("https://example.com", sources=("sitemap", "links"))
			other = crawler.enqueue(on_page=f"{__name__}.record_page")
		self.assertNotEqual(other.name, first.name)
		self.assertEqual(other.source_names(), ("sitemap", "links"))

	def test_enqueued_keyword_priority_is_stored_and_used(self):
		with self.set_user(OWNER):
			crawler = WebCrawler(
				"https://example.com", sources=("links",), priority=KeywordPriority({"Broken": 5})
			)
			web_crawl = crawler.enqueue()
			web_crawl.run()
		self.assertEqual(web_crawl.keyword_weights(), {"broken": 5})
		urls = frappe.get_all(
			"Web Crawl Result", {"web_crawl": web_crawl.name}, pluck="url", order_by="creation asc"
		)
		self.assertEqual(urls, ["https://example.com", "https://example.com/broken", "https://example.com/a"])

	def test_enqueue_refuses_a_priority_it_cannot_store(self):
		with self.set_user(OWNER):
			crawler = WebCrawler("https://example.com", sources=("links",), priority=lambda url, text: 1)
			self.assertRaises(frappe.ValidationError, crawler.enqueue)

	def test_a_crawl_without_tuning_copies_the_settings_tuning(self):
		add_setting_row(self, "link_priorities", {"keyword": "Docs", "weight": 2})
		with self.change_settings("Web Crawl Settings", {"skip_patterns": "/private/"}):
			default = frappe.get_doc({"doctype": "Web Crawl", "url": "https://example.com"}).insert()
			tuned = frappe.get_doc(
				{
					"doctype": "Web Crawl",
					"url": "https://example.com",
					"skip_patterns": "/blog/",
					"link_priorities": [{"keyword": "api", "weight": 1}],
				}
			).insert()
		self.assertEqual((default.keyword_weights(), default.skip_patterns), ({"docs": 2}, "/private/"))
		self.assertEqual((tuned.keyword_weights(), tuned.skip_patterns), ({"api": 1}, "/blog/"))

	def test_sources_default_to_sitemap_then_links(self):
		web_crawl = frappe.get_doc({"doctype": "Web Crawl", "url": "https://example.com"}).insert()
		self.assertEqual(web_crawl.source_names(), ("sitemap", "links"))

	def test_enqueue_ignores_a_crawl_older_than_its_job_timeout(self):
		first = self.start_crawl()
		first.db_set("creation", add_days(now_datetime(), -1))
		self.assertNotEqual(self.start_crawl().name, first.name)

	def test_start_refuses_a_crawl_that_has_started(self):
		web_crawl = self.start_crawl()
		self.assertRaises(frappe.ValidationError, web_crawl.start)

	def test_invalid_url_is_rejected(self):
		web_crawl = frappe.get_doc({"doctype": "Web Crawl", "url": "http://127.0.0.1/"})
		self.assertRaises(frappe.ValidationError, web_crawl.insert)

	def test_blank_limits_come_from_the_settings(self):
		with self.change_settings("Web Crawl Settings", {"max_pages": 20, "max_depth": 3}):
			blank = frappe.get_doc({"doctype": "Web Crawl", "url": "https://example.com"}).insert()
			shallow = frappe.get_doc({"doctype": "Web Crawl", "url": "https://example.com", "max_depth": 0})
			shallow.insert()
		self.assertEqual((blank.max_pages, blank.max_depth), (20, 3))
		self.assertEqual(shallow.max_depth, 0)

	def test_methods_can_only_be_set_from_code(self):
		for fieldname in ("on_page_method", "skip_urls_method"):
			with self.subTest(fieldname=fieldname):
				web_crawl = frappe.get_doc(
					{"doctype": "Web Crawl", "url": "https://example.com", fieldname: "os.system"}
				)
				self.assertRaises(frappe.PermissionError, web_crawl.insert)

	def test_a_retried_run_replaces_the_results(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			web_crawl.run()
			web_crawl.run()
		self.assertEqual(frappe.db.count("Web Crawl Result", {"web_crawl": web_crawl.name}), 2)

	def test_only_the_owner_reads_a_crawl_without_a_reference(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			web_crawl.run()
		result_name = frappe.get_all("Web Crawl Result", {"web_crawl": web_crawl.name}, pluck="name")[0]

		for user, can_read in ((OWNER, True), (STRANGER, False)):
			with self.subTest(user=user), self.set_user(user):
				self.assertEqual(bool(frappe.has_permission("Web Crawl", "read", web_crawl.name)), can_read)
				self.assertEqual(
					bool(frappe.has_permission("Web Crawl Result", "read", result_name)), can_read
				)
				self.assertFalse(frappe.has_permission("Web Crawl", "write", web_crawl.name))

	def test_reference_document_readers_can_read_a_crawl_and_its_results(self):
		for allocated_to, can_read in ((STRANGER, True), (OWNER, False)):
			todo = frappe.get_doc({"doctype": "ToDo", "description": "Crawl", "allocated_to": allocated_to})
			todo.insert(ignore_permissions=True)
			web_crawl = self.start_crawl(reference_doctype="ToDo", reference_name=todo.name)
			with self.set_user(OWNER):
				web_crawl.run()
			result_name = frappe.get_all("Web Crawl Result", {"web_crawl": web_crawl.name}, pluck="name")[0]

			with self.subTest(allocated_to=allocated_to), self.set_user(STRANGER):
				self.assertEqual(bool(frappe.has_permission("Web Crawl", "read", web_crawl.name)), can_read)
				self.assertEqual(
					bool(frappe.has_permission("Web Crawl Result", "read", result_name)), can_read
				)
				self.assertFalse(frappe.has_permission("Web Crawl", "write", web_crawl.name))

	def test_lists_show_only_own_crawls_and_results(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			web_crawl.run()
		for user, expected in ((OWNER, [web_crawl.name]), (STRANGER, [])):
			with self.subTest(user=user), self.set_user(user):
				self.assertEqual(frappe.get_list("Web Crawl", pluck="name"), expected)
				results = frappe.get_list("Web Crawl Result", {"web_crawl": web_crawl.name}, pluck="name")
				self.assertEqual(bool(results), bool(expected))

	def test_only_the_owner_can_stop(self):
		self.enterContext(patch("rq.job.Job.fetch"))
		web_crawl = self.start_crawl()
		self.insert_background_task()
		with self.set_user(STRANGER):
			self.assertRaises(frappe.PermissionError, web_crawl.stop)
		with self.set_user(OWNER):
			web_crawl.stop()
		self.assertEqual(web_crawl.status, "Cancelled")

	def test_stopping_the_background_task_cancels_the_crawl(self):
		from frappe.core.doctype.background_task.background_task import stop_task

		self.enterContext(patch("rq.job.Job.fetch"))
		web_crawl = self.start_crawl()
		self.insert_background_task()
		with self.set_user(OWNER):
			stop_task("task-1")
		web_crawl.reload()
		self.assertEqual(web_crawl.status, "Cancelled")

	def test_old_crawls_are_cleared_with_their_results(self):
		web_crawl = self.start_crawl()
		with self.set_user(OWNER):
			web_crawl.run()
		web_crawl.db_set("creation", add_days(now_datetime(), -31))

		WebCrawl.clear_old_logs(days=30)
		self.assertFalse(frappe.db.exists("Web Crawl", web_crawl.name))
		self.assertFalse(frappe.db.exists("Web Crawl Result", {"web_crawl": web_crawl.name}))
