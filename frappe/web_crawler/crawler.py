import heapq
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from itertools import batched
from urllib.parse import urldefrag

import frappe
from frappe import _
from frappe.web_crawler.fetch import TIME_LIMIT, Fetcher, FetchError
from frappe.web_crawler.limits import CrawlLimits
from frappe.web_crawler.page import CrawledPage, PageParser
from frappe.web_crawler.scope import Robots, Scope, SkipRules, normalize_url
from frappe.web_crawler.sources import LlmsTxt, Sitemap, is_sitemap_url


class WebCrawler:
	"""Reads the pages of one site, within the limits in Web Crawl Settings.

	`index_files` lists pages from the site's llms.txt, then its sitemap.
	`follow_links` follows links breadth first from the start URL, with the listed pages as seeds.
	`previous_hashes` maps URLs to `content_hash` values of an earlier crawl, for each page's `change_status`.
	`priority(url, anchor_text)` orders pages at the same depth (higher first).
	Without `priority` or `skip_patterns`, the tuning in Web Crawl Settings is used.
	`skip_urls(urls)` returns the URLs to drop before they are fetched.
	The crawl stops with `stopped_reason` "time_limit" once the settings' maximum crawl time has passed.
	Pages are read in batches of the settings' concurrent requests, with the request delay between batches.
	A site whose robots.txt sets a Crawl-delay is read one page at a time.
	"""

	def __init__(
		self,
		url: str,
		*,
		index_files: bool = True,
		follow_links: bool = True,
		max_pages: int | None = None,
		max_depth: int | None = None,
		skip_patterns: tuple[str, ...] = (),
		priority: Callable[[str, str], float] | None = None,
		skip_urls: Callable[[list[str]], list[str]] | None = None,
		user_agent: str | None = None,
		previous_hashes: dict[str, str] | None = None,
	):
		self.limits = CrawlLimits.from_settings(max_pages, max_depth, user_agent)
		self.url = self.validate_url(url)
		self.index_files = index_files
		self.follow_links = follow_links
		self.skip_patterns = tuple(skip_patterns) or self.limits.skip_patterns
		self.skip_rules = SkipRules(self.skip_patterns)
		self.previous_hashes = {normalize_url(url): value for url, value in (previous_hashes or {}).items()}
		self.priority = priority or self.settings_priority()
		self.skip_urls = skip_urls
		self.scope = Scope(self.url.rsplit("/", 1)[0] if is_sitemap_url(self.url) else self.url)
		self.stopped_reason: str | None = None
		self.last_request_at = 0.0

	def settings_priority(self) -> "KeywordPriority | None":
		return KeywordPriority(self.limits.link_priorities) if self.limits.link_priorities else None

	def validate_url(self, url: str) -> str:
		from frappe.utils.safe_exec import BlockedRequest, validate_request_url

		url = (url or "").strip()
		if not frappe.utils.validate_url(url, valid_schemes=("http", "https")):
			frappe.throw(_("{0} is not a valid web address").format(url), title=_("Invalid URL"))
		if self.limits.is_blocked(url):
			raise BlockedRequest(_("Web Crawl Settings do not allow the domain of {0}").format(url))
		validate_request_url(url)
		return url

	def find_pages(self) -> list[str]:
		"""Page URLs from the index files, filtered and capped at max_pages."""
		return self.index_urls()[: self.limits.max_pages]

	def index_urls(self) -> list[str]:
		"""llms.txt pages first, as the site picked them, then the sitemap's."""
		if not self.index_files:
			return []
		llms_txt = LlmsTxt(self.fetcher, self.url, self.scope)
		sitemap = Sitemap(self.fetcher, self.url, self.scope, self.robots)
		return self.filter_urls(llms_txt.find() + sitemap.find())

	def crawl(self) -> Iterator[CrawledPage]:
		"""Yields each page as it is read. A failed page is yielded with `error` set; it never raises."""
		for page in self.read_pages(self.frontier()):
			page.compare(self.previous_hashes.get(normalize_url(page.final_url or page.url)))
			yield page

	@cached_property
	def fetcher(self) -> Fetcher:
		return Fetcher(self.limits, deadline=time.monotonic() + self.limits.max_crawl_time)

	@cached_property
	def robots(self) -> Robots:
		return Robots(self.fetcher, self.url)

	def frontier(self) -> "CrawlFrontier":
		"""The start page and its links when following links, and the index files' pages."""
		frontier = CrawlFrontier(self.priority)
		if self.follow_links:
			frontier.add([self.url], 0)
		if not self.follow_links or self.limits.max_depth:
			frontier.add(self.index_urls(), 1)
		return frontier

	def read_pages(self, frontier: "CrawlFrontier") -> Iterator[CrawledPage]:
		read = 0
		while batch := frontier.pop_many(min(self.batch_size(), self.limits.max_pages - read)):
			urls = [url for url, _depth in batch]
			for (url, depth), page in zip(batch, self.read_batch(urls), strict=True):
				if page.error == TIME_LIMIT:
					self.stopped_reason = TIME_LIMIT
					return
				if not frontier.visit(url, page.final_url or url):
					continue
				read += 1
				yield page
				# A 429 that outlived the retries: the rest would 429 too.
				if page.status == 429:
					self.stopped_reason = "rate_limited"
					return
				if self.follow_links and page.ok and depth < self.limits.max_depth:
					frontier.add(self.filter_urls(list(page.links)), depth + 1, page.links)

	def filter_urls(self, urls: list[str]) -> list[str]:
		"""In-scope URLs that robots.txt and the skip rules allow, one per page, minus the caller's skip_urls."""
		allowed = {}
		for url in urls:
			url = urldefrag(url).url
			if (key := normalize_url(url)) not in allowed and self.allows(url):
				allowed[key] = url
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

	def batch_size(self) -> int:
		return 1 if self.robots.crawl_delay() else self.limits.concurrent_requests

	def read_batch(self, urls: list[str]) -> list[CrawledPage]:
		"""The pages of `urls`, fetched at the same time."""
		self.wait()
		with ThreadPoolExecutor(len(urls)) as pool:
			return list(pool.map(self.read_page, urls))

	def read_page(self, url: str) -> CrawledPage:
		page = self.fetch(url)
		if page.error != TIME_LIMIT and not self.scope.contains(page.final_url):
			return CrawledPage(url, page.final_url, page.status, "off_scope")
		return page

	def wait(self):
		if self.last_request_at:
			pause = self.limits.wait_seconds(self.robots.crawl_delay())
			time.sleep(max(self.last_request_at + pause - time.monotonic(), 0))
		self.last_request_at = time.monotonic()


class KeywordPriority:
	"""A `priority` that reads links first when their URL or anchor text has a keyword.
	A link scores the sum of the weights of its keywords. Unlike other callables, it can be enqueued."""

	def __init__(self, weights: dict[str, float]):
		self.weights = {keyword.lower(): weight for keyword, weight in weights.items()}

	def __call__(self, url: str, anchor_text: str) -> float:
		text = f"{url} {anchor_text}".lower()
		return sum(weight for keyword, weight in self.weights.items() if keyword in text)


class CrawlFrontier:
	"""The queue of a link-following crawl: depth first, then the caller's priority, then the order found."""

	def __init__(self, priority: Callable[[str, str], float] | None):
		self.priority = priority
		self.queue: list[tuple[int, float, int, str]] = []
		self.queued: set[str] = set()
		self.visited: set[str] = set()

	def add(self, urls: list[str], depth: int, anchors: dict[str, str] | None = None):
		anchors = {normalize_url(url): text for url, text in (anchors or {}).items()}
		for url in urls:
			key = normalize_url(url)
			if key in self.visited or key in self.queued:
				continue
			score = self.priority(url, anchors.get(key, "")) if self.priority else 0
			heapq.heappush(self.queue, (depth, -score, len(self.queued), url))
			self.queued.add(key)

	def pop_many(self, count: int) -> list[tuple[str, int]]:
		return [item for _ in range(count) if (item := self.pop())]

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
