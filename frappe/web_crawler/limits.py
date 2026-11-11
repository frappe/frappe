from dataclasses import dataclass
from urllib.parse import urlsplit

import frappe

MEGABYTE = 1024 * 1024
# A site asking for a longer wait (Crawl-delay, Retry-After) would stall the job.
MAX_WAIT_SECONDS = 30


@dataclass(frozen=True)
class CrawlLimits:
	"""What one crawl may do, read from Web Crawler Settings. Arguments can only lower the ceilings."""

	max_pages: int
	max_depth: int
	page_timeout: int
	max_page_size: int
	sitemap_timeout: int
	max_sitemap_size: int
	max_redirects: int
	request_delay: float
	user_agent: str
	respect_robots_txt: bool
	blocked_domains: frozenset[str]

	@classmethod
	def from_settings(
		cls, max_pages: int | None = None, max_depth: int | None = None, user_agent: str | None = None
	) -> "CrawlLimits":
		settings = frappe.get_cached_doc("Web Crawler Settings")
		return cls(
			max_pages=lower(settings.max_pages, max_pages),
			max_depth=lower(settings.max_depth, max_depth),
			page_timeout=settings.page_timeout,
			max_page_size=settings.max_page_size * MEGABYTE,
			sitemap_timeout=settings.sitemap_timeout,
			max_sitemap_size=settings.max_sitemap_size * MEGABYTE,
			max_redirects=settings.max_redirects,
			request_delay=settings.request_delay,
			user_agent=user_agent or settings.user_agent,
			respect_robots_txt=bool(settings.respect_robots_txt),
			blocked_domains=frozenset(d.domain.strip(".").lower() for d in settings.blocked_domains),
		)

	def is_blocked(self, url: str) -> bool:
		"""True when the URL's host is a blocked domain or one of its subdomains."""
		host = (urlsplit(url).hostname or "").strip(".")
		return any(host == domain or host.endswith(f".{domain}") for domain in self.blocked_domains)

	def wait_seconds(self, crawl_delay: float | None) -> float:
		"""The pause between two requests: the setting or the site's Crawl-delay, whichever is longer."""
		return min(max(self.request_delay, crawl_delay or 0), MAX_WAIT_SECONDS)


def lower(ceiling: int, requested: int | None) -> int:
	return ceiling if requested is None else max(min(requested, ceiling), 0)
