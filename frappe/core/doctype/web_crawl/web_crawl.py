# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime
from frappe.web_crawler import CrawledPage, WebCrawler
from frappe.web_crawler.limits import CrawlLimits

ACTIVE_STATUSES = ("Queued", "Running")


class WebCrawl(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		background_task: DF.Link | None
		finished_at: DF.Datetime | None
		max_depth: DF.Int
		max_pages: DF.Int
		on_page_method: DF.Data | None
		pages_crawled: DF.Int
		pages_failed: DF.Int
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		skip_patterns: DF.SmallText | None
		skip_urls_method: DF.Data | None
		sources: DF.Data | None
		started_at: DF.Datetime | None
		status: DF.Literal["Queued", "Running", "Completed", "Failed", "Cancelled"]
		stopped_reason: DF.Data | None
		url: DF.SmallText
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl"

	def validate(self):
		self.validate_methods()
		crawler = self.crawler()
		if self.is_new():
			self.max_pages, self.max_depth = crawler.limits.max_pages, crawler.limits.max_depth

	def validate_methods(self):
		"""The methods run in the background job, so only server code may set them."""
		if (
			self.is_new()
			and not self.flags.ignore_permissions
			and (self.on_page_method or self.skip_urls_method)
		):
			frappe.throw(
				_("On page method and Skip URLs method can only be set from code."),
				frappe.PermissionError,
				title=_("Not permitted"),
			)

	def crawler(self, skip_urls=None) -> WebCrawler:
		return WebCrawler(
			self.url,
			sources=tuple(source.strip() for source in (self.sources or "").split(",") if source.strip()),
			max_pages=self.max_pages or None,
			max_depth=self.max_depth,
			skip_patterns=tuple((self.skip_patterns or "").split()),
			skip_urls=skip_urls,
		)

	@classmethod
	def enqueue_crawl(cls, crawler: WebCrawler, on_success=None, on_failure=None, **caller) -> "WebCrawl":
		"""The Web Crawl for `crawler`, started in a background job.
		Returns the user's running crawl instead when it has the same settings and caller."""
		values = {
			"url": crawler.url,
			"sources": ", ".join(crawler.sources),
			"max_pages": crawler.limits.max_pages,
			"max_depth": crawler.limits.max_depth,
			"skip_patterns": "\n".join(crawler.skip_patterns) or None,
			**caller,
		}
		if running := cls.find_running(values, crawler.limits.job_timeout()):
			return running
		web_crawl = frappe.get_doc({"doctype": "Web Crawl", **values})
		web_crawl.insert(ignore_permissions=True)
		web_crawl.enqueue_job(on_success, on_failure)
		return web_crawl

	@staticmethod
	def find_running(values: dict, job_timeout: int) -> "WebCrawl | None":
		"""A crawl older than its job timeout is not running, whatever its status says."""
		filters = {
			**values,
			"owner": frappe.session.user,
			"status": ("in", ACTIVE_STATUSES),
			"background_task": ("is", "set"),
			"creation": (">", add_to_date(now_datetime(), seconds=-job_timeout)),
		}
		if name := frappe.db.get_value("Web Crawl", filters):
			return frappe.get_doc("Web Crawl", name)
		return None

	@frappe.whitelist()
	def start(self):
		self.check_permission("write")
		if self.status != "Queued" or self.background_task:
			frappe.throw(_("This crawl has already started."), title=_("Cannot start"))
		self.enqueue_job()

	@frappe.whitelist()
	def stop(self):
		from frappe.core.doctype.background_task.background_task import stop_task

		if self.status not in ACTIVE_STATUSES or not self.background_task:
			frappe.throw(_("This crawl is not running."), title=_("Cannot stop"))
		stop_task(self.background_task)
		self.reload()

	def enqueue_job(self, on_success=None, on_failure=None):
		task = frappe.enqueue_task(
			"frappe.core.doctype.web_crawl.web_crawl.run_web_crawl",
			task_name=_("Web crawl of {0}").format(self.url),
			queue="long",
			timeout=CrawlLimits.from_settings(self.max_pages or None).job_timeout(),
			ref_doctype=self.doctype,
			ref_docname=self.name,
			on_success=on_success,
			on_failure=on_failure,
			web_crawl=self.name,
		)
		self.db_set("background_task", task.name)

	def run(self) -> dict:
		"""The background job: reads every page, stores it, and calls `on_page_method` in a savepoint.
		A retried job starts over, so the pages of the earlier run are deleted."""
		self.reset_results()
		errors = {}
		try:
			crawler = self.crawler(get_method(self.skip_urls_method))
			on_page = get_method(self.on_page_method)
			for page in crawler.crawl():
				self.save_page(page, on_page, errors)
				self.publish_progress(crawler.limits.max_pages)
		except Exception:
			frappe.db.rollback()
			self.db_set({"status": "Failed", "finished_at": now_datetime()}, commit=True)
			raise
		self.db_set(
			{"status": "Completed", "finished_at": now_datetime(), "stopped_reason": crawler.stopped_reason}
		)
		return self.summary(errors)

	def reset_results(self):
		frappe.db.delete("Web Crawl Page", {"web_crawl": self.name})
		self.db_set(
			{
				"status": "Running",
				"started_at": now_datetime(),
				"finished_at": None,
				"stopped_reason": None,
				"pages_crawled": 0,
				"pages_failed": 0,
			},
			commit=True,
		)

	def save_page(self, page: CrawledPage, on_page, errors: dict):
		error = page.error
		frappe.db.savepoint("web_crawl_page")
		try:
			self.insert_page(page)
			if on_page:
				on_page(page, self)
		except Exception:
			frappe.db.rollback(save_point="web_crawl_page")
			self.log_error(_("Web crawl could not save {0}").format(page.url))
			error = error or "failed"
		if error:
			errors[page.url] = error
		self.pages_crawled += 1
		self.pages_failed += bool(error)
		self.db_set({"pages_crawled": self.pages_crawled, "pages_failed": self.pages_failed}, commit=True)

	def insert_page(self, page: CrawledPage):
		frappe.get_doc(
			{
				"doctype": "Web Crawl Page",
				"web_crawl": self.name,
				"url": page.url,
				"final_url": page.final_url,
				"status_code": page.status,
				"error": page.error,
				"title": page.title,
				"description": page.description,
				"text": page.text,
				"html": page.html,
				"meta_tags": page.meta,
			}
		).insert(ignore_permissions=True)

	def publish_progress(self, max_pages: int):
		from frappe.utils.task_queue import get_current_task

		if task := get_current_task():
			task.publish_progress(min(self.pages_crawled / max(max_pages, 1) * 100, 99))

	def summary(self, errors: dict) -> dict:
		return {
			"pages": self.pages_crawled,
			"ok": self.pages_crawled - self.pages_failed,
			"failed": self.pages_failed,
			"errors": errors,
			"stopped": self.stopped_reason,
		}

	def on_trash(self):
		frappe.db.delete("Web Crawl Page", {"web_crawl": self.name})

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		web_crawl = frappe.qb.DocType("Web Crawl")
		old_crawls = (
			frappe.qb.from_(web_crawl)
			.select(web_crawl.name)
			.where(web_crawl.creation < (Now() - Interval(days=days)))
			.run(pluck=True)
		)
		for name in old_crawls:
			frappe.delete_doc("Web Crawl", name, ignore_permissions=True)


def get_method(path: str | None):
	return frappe.get_attr(path) if path else None


def run_web_crawl(web_crawl: str) -> dict:
	return frappe.get_doc("Web Crawl", web_crawl).run()


def cancel_web_crawl(web_crawl: str):
	frappe.db.set_value("Web Crawl", web_crawl, {"status": "Cancelled", "finished_at": now_datetime()})
