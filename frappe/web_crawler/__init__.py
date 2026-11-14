from frappe.web_crawler.crawler import KeywordPriority, WebCrawler
from frappe.web_crawler.page import CrawledPage


def fetch_page(url: str, *, user_agent: str | None = None) -> CrawledPage:
	"""One page, read within the Web Crawl Settings limits. Raises only for an invalid or blocked URL."""
	return WebCrawler(url, index_files=False, follow_links=False, user_agent=user_agent).fetch(url)


__all__ = ["CrawledPage", "KeywordPriority", "WebCrawler", "fetch_page"]
