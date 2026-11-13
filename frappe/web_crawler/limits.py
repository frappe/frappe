from dataclasses import dataclass
from math import ceil
from urllib.parse import urlsplit

import frappe
from frappe.web_crawler.urls import absolute_url, canonical_host

MEGABYTE = 1024 * 1024
# A site asking for a longer wait (Crawl-delay, Retry-After) would stall the job.
MAX_WAIT_SECONDS = 30
MAX_RETRIES = 2
# A rough time to fetch and parse one page, for the crawl time estimate.
ESTIMATED_PAGE_SECONDS = 1


@dataclass(frozen=True)
class CrawlLimits:
	"""What one crawl may do, read from Web Crawl Settings. Arguments can only lower the ceilings.
	`link_priorities` and `skip_patterns` are the tuning for crawls that set none."""

	max_pages: int
	max_depth: int
	page_timeout: int
	max_page_size: int
	sitemap_timeout: int
	max_sitemap_size: int
	max_redirects: int
	request_delay: float
	concurrent_requests: int
	max_crawl_time: int
	user_agent: str
	respect_robots_txt: bool
	allowed_domains: frozenset[str]
	blocked_domains: frozenset[str]
	link_priorities: dict[str, float]
	skip_patterns: tuple[str, ...]

	@classmethod
	def from_settings(
		cls,
		max_pages: int | None = None,
		max_depth: int | None = None,
		user_agent: str | None = None,
		settings=None,
	) -> "CrawlLimits":
		settings = settings or frappe.get_cached_doc("Web Crawl Settings")
		return cls(
			max_pages=at_most(settings.max_pages, max_pages),
			max_depth=at_most(settings.max_depth, max_depth),
			page_timeout=settings.page_timeout,
			max_page_size=settings.max_page_size * MEGABYTE,
			sitemap_timeout=settings.sitemap_timeout,
			max_sitemap_size=settings.max_sitemap_size * MEGABYTE,
			max_redirects=settings.max_redirects,
			request_delay=settings.request_delay,
			concurrent_requests=settings.concurrent_requests,
			max_crawl_time=settings.max_crawl_time * 60,
			user_agent=user_agent or settings.user_agent,
			respect_robots_txt=bool(settings.respect_robots_txt),
			allowed_domains=domain_set(settings.allowed_domains),
			blocked_domains=domain_set(settings.blocked_domains),
			link_priorities={row.keyword: row.weight for row in settings.link_priorities},
			skip_patterns=tuple((settings.skip_patterns or "").split()),
		)

	def is_blocked(self, url: str) -> bool:
		"""True when the URL's host is a blocked domain, or is not an allowed one when any are set.
		A domain covers its subdomains. A malformed URL is blocked."""
		if not (url := absolute_url(url, url)):
			return True
		host = canonical_host(urlsplit(url).hostname or "")
		if in_domains(host, self.blocked_domains):
			return True
		return bool(self.allowed_domains) and not in_domains(host, self.allowed_domains)

	def wait_seconds(self, crawl_delay: float | None) -> float:
		"""The pause between two batches: the setting or the site's Crawl-delay, whichever is longer."""
		return min(max(self.request_delay, crawl_delay or 0), MAX_WAIT_SECONDS)

	def estimated_crawl_time(self) -> float:
		"""Seconds a full crawl likely takes, before any site's Crawl-delay."""
		batches = ceil(self.max_pages / self.concurrent_requests)
		return batches * (self.request_delay + ESTIMATED_PAGE_SECONDS)

	def job_timeout(self) -> int:
		"""The crawl time, plus the worst case of the request still running when it ends."""
		attempts = MAX_RETRIES + 1
		slowest_request = attempts * (max(self.page_timeout, self.sitemap_timeout) + MAX_WAIT_SECONDS)
		return self.max_crawl_time + slowest_request + MAX_WAIT_SECONDS + 60


def domain_set(rows) -> frozenset[str]:
	return frozenset(canonical_host(row.domain) for row in rows)


def in_domains(host: str, domains: frozenset[str]) -> bool:
	return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def at_most(ceiling: int, requested: int | None) -> int:
	return ceiling if requested is None else max(min(requested, ceiling), 0)
