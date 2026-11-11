import re
from dataclasses import dataclass, field
from functools import cached_property
from urllib.parse import urljoin, urlsplit

import yaml
from bs4 import BeautifulSoup, Tag

from frappe.utils.data import md_to_html, to_markdown
from frappe.utils.html_utils import sanitize_html
from frappe.web_crawler.fetch import Download

NOISE = "nav, footer, aside, script, style, noscript, template, svg"
DISALLOWED_TAGS = ("form", "input", "button", "select", "textarea", "meta", "link", "html", "head", "body")
MARKDOWN_TYPES = ("text/markdown", "text/x-markdown")
FRONT_MATTER = re.compile(r"\A\s*---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
HEADING = re.compile(r"^# (.+)$", re.M)


@dataclass
class CrawledPage:
	"""One fetched page. A failed page has `error` set to a reason code and no content."""

	url: str
	final_url: str = ""
	status: int | None = None
	error: str | None = None
	title: str = ""
	description: str = ""
	meta: dict[str, str] = field(default_factory=dict)
	html: str = ""
	text: str = ""
	raw_html: str = field(default="", repr=False)
	links: dict[str, str] = field(default_factory=dict, repr=False)
	source_markdown: str = field(default="", repr=False)

	@property
	def ok(self) -> bool:
		return self.error is None

	@cached_property
	def markdown(self) -> str:
		"""The page as Markdown: the original source for a `.md` page, else converted from `html`."""
		return self.source_markdown or to_markdown(self.html)


class PageParser:
	"""Turns a download into a Crawled Page: main content, text, title, meta tags and links."""

	def __init__(self, download: Download):
		self.download = download

	def parse(self) -> CrawledPage:
		if self.is_markdown():
			return self.from_markdown()
		if self.download.content_type in ("text/html", "application/xhtml+xml"):
			return self.from_html()
		return self.failed("not_html")

	def is_markdown(self) -> bool:
		path = urlsplit(self.download.final_url).path
		return self.download.content_type in MARKDOWN_TYPES or (
			self.download.content_type == "text/plain" and path.endswith(".md")
		)

	def from_html(self) -> CrawledPage:
		soup = BeautifulSoup(self.download.content, "html.parser", from_encoding=self.download.charset)
		raw_html, links, meta = str(soup), self.links(soup), self.meta(soup)
		main = self.main_content(soup)
		return self.build(
			title=self.title(soup),
			description=meta.get("description") or meta.get("og:description", ""),
			meta=meta,
			main=main,
			raw_html=raw_html,
			links=links,
		)

	def from_markdown(self) -> CrawledPage:
		front_matter, markdown = split_front_matter(self.download.text)
		heading = HEADING.search(markdown)
		title = str(front_matter.get("title") or (heading[1] if heading else "")).strip()
		soup = BeautifulSoup(md_to_html(markdown) or "", "html.parser")
		page = self.build(
			title=title,
			description=str(front_matter.get("description") or ""),
			meta={},
			main=soup,
			raw_html="",
			links=self.links(soup),
		)
		page.source_markdown = markdown
		return page

	def build(self, title, description, meta, main, raw_html, links) -> CrawledPage:
		text = main.get_text("\n", strip=True)
		return CrawledPage(
			url=self.download.url,
			final_url=self.download.final_url,
			status=self.download.status,
			error=None if text else "empty",
			title=title,
			description=description.strip(),
			meta=meta,
			html=sanitize_html(
				self.absolute_links(main), always_sanitize=True, disallowed_tags=DISALLOWED_TAGS
			),
			text=text,
			raw_html=raw_html,
			links=links,
		)

	def main_content(self, soup: BeautifulSoup) -> Tag:
		"""The page's only article, else its main element. A listing page has many articles."""
		for tag in soup.select(NOISE):
			tag.decompose()
		articles = soup.select("article")
		if len(articles) == 1:
			return articles[0]
		return soup.select_one("main, [role=main]") or soup.body or soup

	def title(self, soup: BeautifulSoup) -> str:
		for tag in (soup.title, soup.find("h1")):
			if tag and (title := tag.get_text(" ", strip=True)):
				return title
		return ""

	def meta(self, soup: BeautifulSoup) -> dict[str, str]:
		tags = soup.find_all("meta", content=True)
		return {
			key.lower(): tag["content"] for tag in tags if (key := tag.get("name") or tag.get("property"))
		}

	def links(self, soup: BeautifulSoup) -> dict[str, str]:
		"""Absolute link URLs and their anchor text, in page order."""
		links = {}
		for anchor in soup.find_all("a", href=True):
			url = urljoin(self.download.final_url, anchor["href"])
			links.setdefault(url, anchor.get_text(" ", strip=True))
		return links

	def absolute_links(self, main: Tag) -> str:
		for tag in main.select("a[href], img[src]"):
			attribute = "href" if tag.name == "a" else "src"
			if not tag[attribute].startswith("#"):
				tag[attribute] = urljoin(self.download.final_url, tag[attribute])
		return str(main)

	def failed(self, error: str) -> CrawledPage:
		return CrawledPage(self.download.url, self.download.final_url, self.download.status, error)


def split_front_matter(text: str) -> tuple[dict, str]:
	"""A Markdown page's YAML front matter, and the page without it."""
	match = FRONT_MATTER.match(text)
	if not match:
		return {}, text
	try:
		front_matter = yaml.safe_load(match[1])
	except yaml.YAMLError:
		front_matter = None
	return (front_matter if isinstance(front_matter, dict) else {}), text[match.end() :]
