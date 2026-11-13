from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_link_to_form, now_datetime
from frappe.web_crawler import CrawledPage, KeywordPriority, WebCrawler
from frappe.web_crawler.limits import CrawlLimits
from frappe.website.doctype.web_crawl_settings.web_crawl_settings import warn_if_crawl_may_stop_early

ACTIVE_STATUSES = ("Queued", "Running")
# The fields that make two crawls the same crawl.
CRAWL_FIELDS = (
	"url",
	"index_files",
	"follow_links",
	"max_pages",
	"max_depth",
	"skip_patterns",
	"on_page_method",
	"skip_urls_method",
	"reference_doctype",
	"reference_name",
)
STOPPED_REASONS = {"time_limit": "Time limit", "rate_limited": "Rate limited"}
ERRORS = {
	"blocked": "Blocked",
	"empty": "Empty",
	"failed": "Failed",
	"not_found": "Not found",
	"not_html": "Not HTML",
	"off_scope": "Outside the start URL",
	"server_error": "Server error",
	"timed_out": "Timed out",
	"too_large": "Too large",
	"too_many_redirects": "Too many redirects",
}


class WebCrawl(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.website.doctype.web_crawl_link_priority.web_crawl_link_priority import (
			WebCrawlLinkPriority,
		)

		background_task: DF.Link | None
		finished_at: DF.Datetime | None
		follow_links: DF.Check
		index_files: DF.Check
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
		started_at: DF.Datetime | None
		status: DF.Literal["Queued", "Running", "Completed", "Failed", "Cancelled"]
		stopped_reason: DF.Literal["", "Time limit", "Rate limited"]
		url: DF.SmallText
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl"

	def validate(self):
		if self.is_new():
			self.validate_new()

	def validate_new(self):
		self.validate_methods()
		crawler = self.flags.crawler or self.crawler()
		self.validate_limits(crawler.limits)
		self.apply_settings(crawler)
		if not self.flags.ignore_permissions:
			warn_if_crawl_may_stop_early(crawler.limits)

	def validate_methods(self):
		"""The methods run in the background job, so only server code may set them."""
		if not self.flags.ignore_permissions and (self.on_page_method or self.skip_urls_method):
			frappe.throw(
				_("On page method and Skip URLs method can only be set from code."),
				frappe.PermissionError,
				title=_("Not permitted"),
			)

	def validate_limits(self, limits: CrawlLimits):
		"""Only an admin can raise the limits, in Web Crawl Settings."""
		for fieldname in ("max_pages", "max_depth"):
			if (self.get(fieldname) or 0) > getattr(limits, fieldname):
				frappe.throw(
					_("{0} can be at most {1}. To read more, raise it in {2}.").format(
						_(self.meta.get_label(fieldname)),
						getattr(limits, fieldname),
						get_link_to_form("Web Crawl Settings"),
					),
					title=_("Limit too high"),
				)

	def apply_settings(self, crawler: WebCrawler):
		"""Fills what the crawl leaves blank from Web Crawl Settings, so the crawl shows what it uses."""
		self.max_pages, self.max_depth = crawler.limits.max_pages, crawler.limits.max_depth
		self.skip_patterns = "\n".join(crawler.skip_patterns) or None
		if not self.link_priorities:
			for keyword, weight in crawler.limits.link_priorities.items():
				self.append("link_priorities", {"keyword": keyword, "weight": weight})

	def crawler(self, skip_urls=None, previous_hashes=None) -> WebCrawler:
		"""Blank limits mean the Web Crawl Settings ones; a max depth of 0 reads the start page only."""
		return WebCrawler(
			self.url,
			index_files=bool(self.index_files),
			follow_links=bool(self.follow_links),
			priority=KeywordPriority(self.keyword_weights()) if self.link_priorities else None,
			max_pages=self.max_pages,
			max_depth=self.max_depth,
			skip_patterns=tuple((self.skip_patterns or "").split()),
			skip_urls=skip_urls,
			previous_hashes=previous_hashes,
		)

	def previous_hashes(self) -> dict[str, str]:
		"""Content hashes from the last completed crawl of the same URL, user and reference."""
		filters = {
			"url": self.url,
			"owner": self.owner,
			"reference_doctype": self.reference_doctype,
			"reference_name": self.reference_name,
			"status": "Completed",
			"name": ("!=", self.name),
		}
		previous = frappe.get_all("Web Crawl", filters, pluck="name", order_by="creation desc", limit=1)
		if not previous:
			return {}
		results = frappe.get_all(
			"Web Crawl Result",
			{"web_crawl": previous[0], "content_hash": ("is", "set")},
			["url", "final_url", "content_hash"],
		)
		return {result.final_url or result.url: result.content_hash for result in results}

	def keyword_weights(self) -> dict[str, float]:
		return {row.keyword: row.weight for row in self.link_priorities}

	def find_running(self, on_success: str | None = None, on_failure: str | None = None) -> "WebCrawl | None":
		"""The user's crawl with the same fields and callbacks that is still running.
		A crawl older than its job timeout is not running, whatever its status says.
		Locking reads, so they also see a crawl committed while `enqueue_crawl` waited for its lock."""
		filters = {
			**{fieldname: self.get(fieldname) for fieldname in CRAWL_FIELDS},
			"owner": frappe.session.user,
			"status": ("in", ACTIVE_STATUSES),
			"background_task": ("is", "set"),
			"creation": (
				">",
				add_to_date(now_datetime(), seconds=-CrawlLimits.from_settings().job_timeout()),
			),
		}
		crawls = frappe.db.get_values("Web Crawl", filters, ["name", "background_task"], for_update=True)
		if not crawls:
			return None
		callbacks = {"on_success_callback": on_success, "on_failure_callback": on_failure}
		task_filters = {"name": ("in", [task for _name, task in crawls]), **callbacks}
		tasks = frappe.db.get_values("Background Task", task_filters, pluck=True, for_update=True)
		names = [name for name, task in crawls if task in tasks]
		if not names:
			return None
		weights = defaultdict(dict)
		priority_filters = {"parenttype": "Web Crawl", "parent": ("in", names)}
		for parent, keyword, weight in frappe.db.get_values(
			"Web Crawl Link Priority", priority_filters, ["parent", "keyword", "weight"], for_update=True
		):
			weights[parent][keyword] = weight
		name = next((name for name in names if weights[name] == self.keyword_weights()), None)
		return frappe.get_doc("Web Crawl", name, for_update=True) if name else None

	@frappe.whitelist()
	def stop(self):
		from frappe.core.doctype.background_task.background_task import stop_task

		if self.owner != frappe.session.user:
			self.check_permission("write")
		if self.status not in ACTIVE_STATUSES or not self.background_task:
			frappe.throw(_("This crawl is not running."), title=_("Cannot stop"))
		stop_task(self.background_task)
		self.reload()

	def after_insert(self):
		task = frappe.enqueue_task(
			"frappe.website.doctype.web_crawl.web_crawl.run_web_crawl",
			task_name=_("Web crawl of {0}").format(self.url)[:140],  # Background Task's Data length
			queue="long",
			timeout=CrawlLimits.from_settings().job_timeout(),
			ref_doctype=self.doctype,
			ref_docname=self.name,
			on_success=self.flags.on_success,
			on_failure=self.flags.on_failure,
			web_crawl=self.name,
		)
		self.db_set("background_task", task.name)

	def run(self) -> dict:
		"""The background job: reads every page, stores it, and calls `on_page_method` in a savepoint.
		A retried job starts over, so the pages of the earlier run are deleted."""
		self.reset_results()
		errors = {}
		try:
			crawler = self.crawler(get_method(self.skip_urls_method), self.previous_hashes())
			on_page = get_method(self.on_page_method)
			for page in crawler.crawl():
				self.save_page(page, on_page, errors)
				self.publish_progress(crawler.limits.max_pages)
		except Exception:
			frappe.db.rollback()
			self.db_set({"status": "Failed", "finished_at": now_datetime()}, commit=True)
			raise
		self.db_set(
			{
				"status": "Completed",
				"finished_at": now_datetime(),
				"stopped_reason": STOPPED_REASONS.get(crawler.stopped_reason),
			}
		)
		return self.summary(errors, crawler.stopped_reason)

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
		self.db_set(
			{"pages_crawled": self.pages_crawled, "pages_failed": self.pages_failed},
			commit=True,
			update_modified=False,
		)

	def insert_result(self, page: CrawledPage):
		frappe.get_doc(
			{
				"doctype": "Web Crawl Result",
				"web_crawl": self.name,
				"url": page.url,
				"final_url": page.final_url,
				"status_code": page.status,
				"content_hash": page.content_hash,
				"error": ERRORS[page.error] if page.error else None,
				"change_status": page.change_status,
				"title": page.title or page.url,
				"description": page.description,
				"html": page.html,
				"meta_tags": page.meta,
			}
		).insert(ignore_permissions=True)

	def publish_progress(self, max_pages: int):
		from frappe.utils.task_queue import get_current_task

		if task := get_current_task():
			task.publish_progress(min(self.pages_crawled / max(max_pages, 1) * 100, 99))

	def summary(self, errors: dict, stopped_reason: str | None) -> dict:
		return {
			"pages": self.pages_crawled,
			"ok": self.pages_crawled - self.pages_failed,
			"failed": self.pages_failed,
			"errors": errors,
			"stopped": stopped_reason,
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
		if not old_crawls:
			return
		frappe.db.delete("Web Crawl Result", {"web_crawl": ("in", old_crawls)})
		frappe.db.delete("Web Crawl Link Priority", {"parenttype": "Web Crawl", "parent": ("in", old_crawls)})
		frappe.db.delete("Web Crawl", {"name": ("in", old_crawls)})


def enqueue_crawl(
	url: str,
	*,
	on_page: str | None = None,
	skip_urls: str | None = None,
	on_success: str | None = None,
	on_failure: str | None = None,
	**fields,
) -> WebCrawl:
	"""Crawls `url` in a background job and returns its Web Crawl, or the user's running one with
	the same fields. `on_page(page, web_crawl)` and `skip_urls(urls)` are dotted paths, called in the job.
	`fields` are other Web Crawl fields, such as `follow_links`, `max_pages` or `reference_name`.
	Locks the user's row until the caller's transaction ends."""
	web_crawl = frappe.new_doc("Web Crawl")
	web_crawl.update({"url": url, "on_page_method": on_page, "skip_urls_method": skip_urls, **fields})
	web_crawl.flags.update(crawler=web_crawl.crawler(), on_success=on_success, on_failure=on_failure)
	web_crawl.apply_settings(web_crawl.flags.crawler)
	# Waits for the user's other enqueue_crawl calls to commit, so identical calls start one crawl.
	frappe.db.get_value("User", frappe.session.user, "name", for_update=True)
	if running := web_crawl.find_running(on_success, on_failure):
		return running
	web_crawl.insert(ignore_permissions=True)
	return web_crawl


def get_method(path: str | None):
	return frappe.get_attr(path) if path else None


def run_web_crawl(web_crawl: str) -> dict:
	return frappe.get_doc("Web Crawl", web_crawl).run()


def cancel_web_crawl(web_crawl: str):
	frappe.db.set_value("Web Crawl", web_crawl, {"status": "Cancelled", "finished_at": now_datetime()})


def has_permission(doc, ptype: str | None = None, user: str | None = None, debug=False) -> bool:
	"""Others' crawls are readable through read access to the crawl's reference document."""
	user = user or frappe.session.user
	if doc.owner == user or can_manage_crawls(user):
		return True
	if ptype not in ("read", "select") or not (doc.reference_doctype and doc.reference_name):
		return False
	return bool(frappe.has_permission(doc.reference_doctype, "read", doc.reference_name, user=user))


def get_permission_query_conditions(user: str | None = None) -> str | None:
	return owner_condition(user)


def owner_condition(user: str | None = None) -> str | None:
	"""Lists show only the user's own crawls, because reference access can't be a query condition."""
	user = user or frappe.session.user
	if can_manage_crawls(user):
		return None
	return f"`tabWeb Crawl`.`owner` = {frappe.db.escape(user)}"


def can_manage_crawls(user: str) -> bool:
	"""Users whose roles can write any Web Crawl see every crawl."""
	return frappe.has_permission("Web Crawl", "write", user=user, ignore_share_permissions=True)


def on_doctype_update():
	frappe.db.add_index("Web Crawl", ["owner", "status"])
