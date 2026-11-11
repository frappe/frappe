import heapq
import time
from collections.abc import Callable, Iterator
from functools import cached_property
from urllib.parse import urldefrag

import frappe
from frappe import _
from frappe.web_crawler.fetch import TIME_LIMIT, Fetcher, FetchError
from frappe.web_crawler.limits import CrawlLimits
from frappe.web_crawler.page import CrawledPage, PageParser
from frappe.web_crawler.scope import Robots, Scope, SkipRules, normalize_url
from frappe.web_crawler.sources import LlmsTxt, Sitemap, is_sitemap_url

DEFAULT_SOURCES = ("sitemap", "links")
LIST_SOURCES = ("sitemap", "llms.txt")


class WebCrawler:
	"""Reads the pages of one site, within the limits in Web Crawler Settings.

	`sources` without "links" lists pages from the first of sitemap / llms.txt that has any.
	With "links", links are followed breadth first from the start URL, with sitemap pages as seeds.
	`priority(url, anchor_text)` orders pages at the same depth (higher first).
	`skip_urls(urls)` returns the URLs to drop before they are fetched.
	The crawl stops with `stopped_reason` "time_limit" once the settings' maximum crawl time has passed.
	"""

	def __init__(
		self,
		url: str,
		*,
		sources: tuple[str, ...] = DEFAULT_SOURCES,
		max_pages: int | None = None,
		max_depth: int | None = None,
		skip_patterns: tuple[str, ...] = (),
		priority: Callable[[str, str], float] | None = None,
		skip_urls: Callable[[list[str]], list[str]] | None = None,
		user_agent: str | None = None,
	):
		self.limits = CrawlLimits.from_settings(max_pages, max_depth, user_agent)
		self.url = self.validate_url(url)
		self.sources = self.validate_sources(sources)
		self.skip_patterns = tuple(skip_patterns)
		self.skip_rules = SkipRules(self.skip_patterns)
		self.priority = priority
		self.skip_urls = skip_urls
		self.scope = Scope(self.url.rsplit("/", 1)[0] if is_sitemap_url(self.url) else self.url)
		self.stopped_reason: str | None = None
		self.last_request_at = 0.0

	def validate_url(self, url: str) -> str:
		from frappe.utils.safe_exec import BlockedRequest, validate_request_url

		url = (url or "").strip()
		if not frappe.utils.validate_url(url, valid_schemes=("http", "https")):
			frappe.throw(_("{0} is not a valid web address").format(url), title=_("Invalid URL"))
		if self.limits.is_blocked(url):
			raise BlockedRequest(_("The domain of {0} is blocked in Web Crawler Settings").format(url))
		validate_request_url(url)
		return url

	def validate_sources(self, sources: tuple[str, ...]) -> tuple[str, ...]:
		if unknown := set(sources) - {*LIST_SOURCES, "links"}:
			frappe.throw(_("Unknown crawl sources: {0}").format(", ".join(sorted(unknown))))
		return tuple(sources)

	def find_pages(self) -> list[str]:
		"""Page URLs from the first list source that has any, filtered and capped at max_pages."""
		for source in self.sources:
			if source in LIST_SOURCES and (urls := self.filter_urls(self.list_source(source).find())):
				return urls[: self.limits.max_pages]
		return []

	def crawl(self) -> Iterator[CrawledPage]:
		"""Yields each page as it is read. A failed page is yielded with `error` set; it never raises."""
		if "links" in self.sources:
			yield from self.follow_links()
		else:
			yield from self.read_pages(self.find_pages())

	def enqueue(
		self,
		on_page: str | None = None,
		*,
		skip_urls: str | None = None,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		on_success: str | None = None,
		on_failure: str | None = None,
	):
		"""Runs the crawl in a background job and stores it as a Web Crawl, which is returned.
		`on_page(page, web_crawl)` and `skip_urls(urls)` are dotted paths, called in the job."""
		from frappe.core.doctype.web_crawl.web_crawl import WebCrawl

		return WebCrawl.enqueue_crawl(
			self,
			on_page_method=on_page,
			skip_urls_method=skip_urls,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			on_success=on_success,
			on_failure=on_failure,
		)

	@cached_property
	def fetcher(self) -> Fetcher:
		return Fetcher(self.limits, deadline=time.monotonic() + self.limits.max_crawl_time)

	@cached_property
	def robots(self) -> Robots:
		return Robots(self.fetcher, self.url)

	def list_source(self, source: str) -> Sitemap | LlmsTxt:
		if source == "sitemap":
			return Sitemap(self.fetcher, self.url, self.scope, self.robots)
		return LlmsTxt(self.fetcher, self.url, self.scope)

	def read_pages(self, urls: list[str]) -> Iterator[CrawledPage]:
		seen = set()
		for url in urls:
			if not (page := self.read(url)):
				return
			if normalize_url(page.final_url or url) in seen:
				continue
			seen.add(normalize_url(page.final_url or url))
			yield page
			if self.should_stop(page):
				return

	def follow_links(self) -> Iterator[CrawledPage]:
		frontier = CrawlFrontier(self.url, self.priority)
		if "sitemap" in self.sources and self.limits.max_depth:
			frontier.add(self.filter_urls(self.list_source("sitemap").find()), 1)
		read = 0
		while read < self.limits.max_pages and (item := frontier.pop()):
			url, depth = item
			if not (page := self.read(url)):
				return
			if not frontier.visit(url, page.final_url or url):
				continue
			read += 1
			yield page
			if self.should_stop(page):
				return
			if page.ok and depth < self.limits.max_depth:
				frontier.add(self.filter_urls(list(page.links)), depth + 1, page.links)

	def filter_urls(self, urls: list[str]) -> list[str]:
		"""In-scope URLs that robots.txt and the skip rules allow, one per page, minus the caller's skip_urls."""
		allowed = {}
		for url in urls:
			url = urldefrag(url).url
			if normalize_url(url) not in allowed and self.allows(url):
				allowed[normalize_url(url)] = url
		urls = list(allowed.values())
		if not (self.skip_urls and urls):
			return urls
		skipped = set(self.skip_urls(urls))
		return [url for url in urls if url not in skipped]

	def allows(self, url: str) -> bool:
		return self.scope.contains(url) and not self.skip_rules.skips(url) and self.robots.allows(url)

	def fetch(self, url: str) -> CrawledPage:
		"""One page, wherever its redirects lead."""
		try:
			download = self.fetcher.get(url, self.limits.max_page_size, self.limits.page_timeout)
		except FetchError as e:
			return CrawledPage(url, e.final_url or url, e.status, e.code)
		return PageParser(download).parse()

	def read(self, url: str) -> CrawledPage | None:
		"""The next page of the crawl, or None once the crawl is out of time."""
		self.wait()
		page = self.fetch(url)
		if page.error == TIME_LIMIT:
			self.stopped_reason = TIME_LIMIT
			return None
		if not self.scope.contains(page.final_url):
			return CrawledPage(url, page.final_url, page.status, "off_scope")
		return page

	def wait(self):
		if self.last_request_at:
			pause = self.limits.wait_seconds(self.robots.crawl_delay())
			time.sleep(max(self.last_request_at + pause - time.monotonic(), 0))
		self.last_request_at = time.monotonic()

	def should_stop(self, page: CrawledPage) -> bool:
		"""A 429 that outlived the retries means the site wants us gone; the rest would 429 too."""
		if page.status == 429:
			self.stopped_reason = "rate_limited"
		return bool(self.stopped_reason)


class CrawlFrontier:
	"""The queue of a link-following crawl: depth first, then the caller's priority, then the order found."""

	def __init__(self, start_url: str, priority: Callable[[str, str], float] | None):
		self.priority = priority
		self.queue: list[tuple[int, float, int, str]] = []
		self.queued: set[str] = set()
		self.visited: set[str] = set()
		self.add([start_url], 0)

	def add(self, urls: list[str], depth: int, anchors: dict[str, str] | None = None):
		anchors = {normalize_url(url): text for url, text in (anchors or {}).items()}
		for url in urls:
			key = normalize_url(url)
			if key in self.visited or key in self.queued:
				continue
			score = self.priority(url, anchors.get(key, "")) if self.priority else 0
			heapq.heappush(self.queue, (depth, -score, len(self.queued), url))
			self.queued.add(key)

	def pop(self) -> tuple[str, int] | None:
		while self.queue:
			depth, _score, _order, url = heapq.heappop(self.queue)
			if normalize_url(url) not in self.visited:
				return url, depth
		return None

	def visit(self, url: str, final_url: str) -> bool:
		"""Marks a page read; False when a redirect led to a page already read."""
		final_url = normalize_url(final_url)
		is_new = final_url not in self.visited
		self.visited.update((normalize_url(url), final_url))
		return is_new
