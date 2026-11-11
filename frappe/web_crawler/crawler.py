import time
from collections.abc import Callable, Iterator
from functools import cached_property

import frappe
from frappe import _
from frappe.web_crawler.fetch import Fetcher, FetchError
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
			raise BlockedRequest(_("{0} is a blocked domain in Web Crawler Settings").format(url))
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

	@cached_property
	def fetcher(self) -> Fetcher:
		return Fetcher(self.limits)

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
			page = self.fetch(url)
			if normalize_url(page.final_url or url) in seen:
				continue
			seen.add(normalize_url(page.final_url or url))
			yield page
			if self.should_stop(page):
				return

	def follow_links(self) -> Iterator[CrawledPage]:
		frontier = CrawlFrontier(self.url, self.priority)
		if "sitemap" in self.sources:
			frontier.add(self.filter_urls(Sitemap(self.fetcher, self.url, self.scope, self.robots).find()), 1)
		read = 0
		while read < self.limits.max_pages and (item := frontier.pop()):
			url, depth = item
			page = self.fetch(url)
			if not frontier.visit(url, page.final_url or url):
				continue
			read += 1
			yield page
			if self.should_stop(page):
				return
			if page.ok and depth < self.limits.max_depth:
				frontier.add(self.filter_urls(list(page.links)), depth + 1, page.links)

	def filter_urls(self, urls: list[str]) -> list[str]:
		"""In-scope URLs that robots.txt and the skip rules allow, minus the caller's skip_urls."""
		urls = list(
			dict.fromkeys(
				normalize_url(url)
				for url in urls
				if self.scope.contains(url) and not self.skip_rules.skips(url) and self.robots.allows(url)
			)
		)
		if not (self.skip_urls and urls):
			return urls
		skipped = set(self.skip_urls(urls))
		return [url for url in urls if url not in skipped]

	def fetch(self, url: str) -> CrawledPage:
		self.wait()
		try:
			download = self.fetcher.get(url, self.limits.max_page_size, self.limits.page_timeout)
		except FetchError as e:
			return CrawledPage(url, e.final_url or url, e.status, e.code)
		if not self.scope.contains(download.final_url):
			return CrawledPage(url, download.final_url, download.status, "off_scope")
		return PageParser(download).parse()

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
	"""The queue of a link-following crawl: depth first, then the caller's priority."""

	def __init__(self, start_url: str, priority: Callable[[str, str], float] | None):
		self.priority = priority
		self.queue: dict[str, tuple[int, float]] = {normalize_url(start_url): (0, 0)}
		self.visited: set[str] = set()

	def add(self, urls: list[str], depth: int, anchors: dict[str, str] | None = None):
		anchors = {normalize_url(url): text for url, text in (anchors or {}).items()}
		for url in urls:
			if url not in self.visited and url not in self.queue:
				score = self.priority(url, anchors.get(url, "")) if self.priority else 0
				self.queue[url] = (depth, -score)

	def pop(self) -> tuple[str, int] | None:
		if not self.queue:
			return None
		url = min(self.queue, key=self.queue.get)
		depth, _score = self.queue.pop(url)
		return url, depth

	def visit(self, url: str, final_url: str) -> bool:
		"""Marks a page read; False when a redirect led to a page already read."""
		final_url = normalize_url(final_url)
		is_new = final_url not in self.visited
		for read_url in (normalize_url(url), final_url):
			self.visited.add(read_url)
			self.queue.pop(read_url, None)
		return is_new
