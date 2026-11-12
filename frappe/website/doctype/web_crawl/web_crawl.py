# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime
from frappe.web_crawler import CrawledPage, KeywordPriority, WebCrawler
from frappe.web_crawler.crawler import DEFAULT_SOURCES
from frappe.web_crawler.limits import CrawlLimits

ACTIVE_STATUSES = ("Queued", "Running")


class WebCrawl(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.website.doctype.web_crawl_link_priority.web_crawl_link_priority import (
			WebCrawlLinkPriority,
		)
		from frappe.website.doctype.web_crawl_source_item.web_crawl_source_item import WebCrawlSourceItem

		background_task: DF.Link | None
		finished_at: DF.Datetime | None
		link_priorities: DF.Table[WebCrawlLinkPriority]
		max_depth: DF.Int
		max_pages: DF.Int
		on_page_method: DF.Data | None
		pages_crawled: DF.Int
		pages_failed: DF.Int
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		skip_patterns: DF.SmallText | None
		skip_urls_method: DF.Data | None
		sources: DF.TableMultiSelect[WebCrawlSourceItem]
		started_at: DF.Datetime | None
		status: DF.Literal["Queued", "Running", "Completed", "Failed", "Cancelled"]
		stopped_reason: DF.Data | None
		url: DF.SmallText
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl"

	def validate(self):
		self.validate_methods()
		if self.is_new() and not self.sources:
			self.set("sources", [{"source": source} for source in DEFAULT_SOURCES])
		crawler = self.crawler()
		if self.is_new():
			self.max_pages, self.max_depth = crawler.limits.max_pages, crawler.limits.max_depth
			self.copy_tuning(crawler)
			if not self.flags.ignore_permissions:
				crawler.limits.warn_if_crawl_may_stop_early()

	def copy_tuning(self, crawler: WebCrawler):
		"""Stores the settings' tuning on a crawl that sets none, so the crawl shows what it uses."""
		if not self.link_priorities:
			for keyword, weight in stored_keyword_weights(crawler).items():
				self.append("link_priorities", {"keyword": keyword, "weight": weight})
		self.skip_patterns = "\n".join(crawler.skip_patterns) or None

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
			sources=self.source_names(),
			priority=KeywordPriority(self.keyword_weights()) if self.link_priorities else None,
			max_pages=self.max_pages or None,
			max_depth=self.max_depth,
			skip_patterns=tuple((self.skip_patterns or "").split()),
			skip_urls=skip_urls,
		)

	def source_names(self) -> tuple[str, ...]:
		return tuple(row.source for row in self.sources)

	def keyword_weights(self) -> dict[str, float]:
		return {row.keyword.lower(): row.weight for row in self.link_priorities}

	@classmethod
	def enqueue_crawl(cls, crawler: WebCrawler, on_success=None, on_failure=None, **caller) -> "WebCrawl":
		"""The Web Crawl for `crawler`, started in a background job.
		Returns the user's running crawl instead when it has the same settings and caller."""
		values = {
			"url": crawler.url,
			"max_pages": crawler.limits.max_pages,
			"max_depth": crawler.limits.max_depth,
			"skip_patterns": "\n".join(crawler.skip_patterns) or None,
			**caller,
		}
		if running := cls.find_running(values, crawler):
			return running
		web_crawl = frappe.get_doc(
			{
				"doctype": "Web Crawl",
				"sources": [{"source": source} for source in crawler.sources],
				"link_priorities": [
					{"keyword": keyword, "weight": weight}
					for keyword, weight in stored_keyword_weights(crawler).items()
				],
				**values,
			}
		)
		web_crawl.insert(ignore_permissions=True)
		web_crawl.enqueue_job(on_success, on_failure)
		return web_crawl

	@staticmethod
	def find_running(values: dict, crawler: WebCrawler) -> "WebCrawl | None":
		"""A crawl older than its job timeout is not running, whatever its status says."""
		filters = {
			**values,
			"owner": frappe.session.user,
			"status": ("in", ACTIVE_STATUSES),
			"background_task": ("is", "set"),
			"creation": (">", add_to_date(now_datetime(), seconds=-crawler.limits.job_timeout())),
		}
		for name in frappe.get_all("Web Crawl", filters=filters, pluck="name"):
			web_crawl = frappe.get_doc("Web Crawl", name)
			if (web_crawl.source_names(), web_crawl.keyword_weights()) == (
				crawler.sources,
				stored_keyword_weights(crawler),
			):
				return web_crawl
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
			"frappe.website.doctype.web_crawl.web_crawl.run_web_crawl",
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
		frappe.db.delete("Web Crawl Result", {"web_crawl": self.name})
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
		frappe.db.savepoint("web_crawl_result")
		try:
			self.insert_result(page)
			if on_page:
				on_page(page, self)
		except Exception:
			frappe.db.rollback(save_point="web_crawl_result")
			self.log_error(_("Web crawl could not save {0}").format(page.url))
			error = error or "failed"
		if error:
			errors[page.url] = error
		self.pages_crawled += 1
		self.pages_failed += bool(error)
		self.db_set({"pages_crawled": self.pages_crawled, "pages_failed": self.pages_failed}, commit=True)

	def insert_result(self, page: CrawledPage):
		frappe.get_doc(
			{
				"doctype": "Web Crawl Result",
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
		frappe.db.delete("Web Crawl Result", {"web_crawl": self.name})

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


def stored_keyword_weights(crawler: WebCrawler) -> dict[str, float]:
	"""The crawler's keyword weights. Only a KeywordPriority can be stored with an enqueued crawl."""
	if crawler.priority is None:
		return {}
	if not isinstance(crawler.priority, KeywordPriority):
		frappe.throw(
			_("An enqueued crawl can only use a KeywordPriority as its priority."), title=_("Cannot enqueue")
		)
	return crawler.priority.weights


def get_method(path: str | None):
	return frappe.get_attr(path) if path else None


def run_web_crawl(web_crawl: str) -> dict:
	return frappe.get_doc("Web Crawl", web_crawl).run()


def cancel_web_crawl(web_crawl: str):
	frappe.db.set_value("Web Crawl", web_crawl, {"status": "Cancelled", "finished_at": now_datetime()})


def has_permission(doc: WebCrawl, ptype: str | None = None, user: str | None = None, debug=False) -> bool:
	"""Others' crawls are readable through read access to the crawl's reference document."""
	user = user or frappe.session.user
	if doc.owner == user or "System Manager" in frappe.get_roles(user):
		return True
	if ptype not in ("read", "select") or not (doc.reference_doctype and doc.reference_name):
		return False
	return bool(frappe.has_permission(doc.reference_doctype, "read", doc.reference_name, user=user))


def get_permission_query_conditions(user: str | None = None) -> str | None:
	return owner_condition("Web Crawl", user)


def owner_condition(doctype: str, user: str | None = None) -> str | None:
	"""Lists show only the user's own crawls, because reference access can't be a query condition."""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return None
	return f"`tab{doctype}`.`owner` = {frappe.db.escape(user)}"
