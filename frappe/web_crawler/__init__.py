from collections.abc import Iterator

from frappe.web_crawler.crawler import KeywordPriority, WebCrawler
from frappe.web_crawler.page import CrawledPage


def scrape(url: str, *, user_agent: str | None = None) -> CrawledPage:
	"""One page, read now within the Web Crawl Settings limits. Raises only for an invalid or blocked URL."""
	return WebCrawler(url, sitemap="skip", user_agent=user_agent).fetch(url)


def list_pages(url: str, *, limit: int | None = None, **options) -> list[str]:
	"""The page URLs a site lists in its llms.txt and sitemap.xml, without reading the pages."""
	return WebCrawler(url, sitemap="only", limit=limit, **options).list_pages()


def crawl(url: str, **options) -> Iterator[CrawledPage]:
	"""Reads a site now and yields each page. `options` are those of `WebCrawler`."""
	return WebCrawler(url, **options).crawl()


def start_crawl(url: str, **options):
	"""Crawls a site in a background job and returns its Web Crawl. See `web_crawl.start_crawl`."""
	from frappe.website.doctype.web_crawl.web_crawl import start_crawl

	return start_crawl(url, **options)


__all__ = ["CrawledPage", "KeywordPriority", "WebCrawler", "crawl", "list_pages", "scrape", "start_crawl"]
