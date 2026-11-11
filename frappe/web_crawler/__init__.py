from frappe.web_crawler.crawler import WebCrawler
from frappe.web_crawler.page import CrawledPage


def fetch_page(url: str, *, user_agent: str | None = None) -> CrawledPage:
	"""One page, read within the Web Crawler Settings limits. Raises only for an invalid or blocked URL."""
	return WebCrawler(url, sources=(), user_agent=user_agent).fetch(url)


__all__ = ["CrawledPage", "WebCrawler", "fetch_page"]
