import re
from html import unescape
from urllib.parse import urljoin, urlsplit

from frappe.web_crawler.fetch import Download, Fetcher, FetchError
from frappe.web_crawler.scope import Robots, Scope, bare_host, site_root

# Most pages a source may list, and most child sitemaps or indexes it may follow.
MAX_CANDIDATES = 2000
MAX_CHILDREN = 5
LOC = re.compile(r"<loc>([^<]*)</loc>")
LLMS_LINK = re.compile(r"^\s*[-*] \[(.+?)\]\((\S+?)\)", re.M)
# Mintlify lists big sites as /_llms/<section>.txt.
LLMS_CHILD_INDEX = re.compile(r"/llms\.txt$|/_llms/.+\.txt$")


def is_sitemap_url(url: str) -> bool:
	return urlsplit(url).path.endswith(".xml")


class Source:
	"""Finds a site's page URLs from one index file, without reading the pages."""

	def __init__(self, fetcher: Fetcher, start_url: str, scope: Scope):
		self.fetcher = fetcher
		self.start_url = start_url.rstrip("/")
		self.scope = scope

	def find(self) -> list[str]:
		raise NotImplementedError

	def read(self, url: str) -> Download | None:
		"""An index file, or None when it is missing, unreadable or an HTML page."""
		limits = self.fetcher.limits
		try:
			download = self.fetcher.get(url, limits.max_sitemap_size, limits.sitemap_timeout)
		except FetchError:
			return None
		return None if download.content_type == "text/html" else download

	def in_scope(self, urls) -> list[str]:
		return list(dict.fromkeys(url for url in urls if self.scope.contains(url)))[:MAX_CANDIDATES]


class Sitemap(Source):
	"""sitemap.xml: under the start path, at the site root, then the ones robots.txt names.
	A sitemap index is followed one level deep."""

	def __init__(self, fetcher: Fetcher, start_url: str, scope: Scope, robots: Robots):
		super().__init__(fetcher, start_url, scope)
		self.robots = robots

	def find(self) -> list[str]:
		for url in self.candidates():
			if locs := self.locs(url):
				return self.in_scope(locs)
		return []

	def candidates(self) -> list[str]:
		if is_sitemap_url(self.start_url):
			return [self.start_url]
		named = [url for url in self.robots.sitemaps() if bare_host(url) == self.scope.host]
		root = site_root(self.start_url)
		return list(dict.fromkeys([f"{self.start_url}/sitemap.xml", f"{root}/sitemap.xml", *named]))

	def locs(self, url: str) -> list[str]:
		download = self.read(url)
		if not download or "<!DOCTYPE" in download.text or "<!ENTITY" in download.text:
			return []
		text = download.text.replace("<![CDATA[", "").replace("]]>", "")
		locs = [unescape(loc.strip()) for loc in LOC.findall(text)]
		if "<sitemapindex" in text:
			return self.child_locs(locs)
		return locs if "<urlset" in text else []

	def child_locs(self, children: list[str]) -> list[str]:
		locs = []
		for child in [url for url in children if bare_host(url) == self.scope.host][:MAX_CHILDREN]:
			download = self.read(child)
			if download and "<urlset" in download.text and "<!DOCTYPE" not in download.text:
				locs += [unescape(loc.strip()) for loc in LOC.findall(download.text)]
		return locs


class LlmsTxt(Source):
	"""llms.txt under the start path: its page links in order, following child indexes one level."""

	def find(self) -> list[str]:
		pages, children = self.parse(f"{self.start_url}/llms.txt")
		for child in children[:MAX_CHILDREN]:
			pages += self.parse(child)[0]
		return self.in_scope(pages)

	def parse(self, url: str) -> tuple[list[str], list[str]]:
		download = self.read(url)
		if not download:
			return [], []
		pages, children = [], []
		for _title, link in LLMS_LINK.findall(download.text):
			link = urljoin(url, link)
			is_index = LLMS_CHILD_INDEX.search(urlsplit(link).path)
			(children if is_index else pages).append(link)
		return pages, list(dict.fromkeys(children))
