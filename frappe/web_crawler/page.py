import re
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from urllib.parse import urlsplit

import nh3
import yaml
from bs4 import BeautifulSoup, CData, NavigableString, Tag

from frappe.core.doctype.file.utils import get_content_hash
from frappe.utils.data import md_to_html, to_markdown
from frappe.utils.html_utils import acceptable_attributes, acceptable_elements, mathml_elements
from frappe.web_crawler.fetch import Download
from frappe.web_crawler.urls import absolute_url

NOISE = "nav, footer, aside, script, style, noscript, template, svg"
DISALLOWED_TAGS = ("form", "input", "button", "select", "textarea", "meta", "link", "html", "head", "body")
MARKDOWN_TYPES = ("text/markdown", "text/x-markdown")
FRONT_MATTER = re.compile(r"\A\s*---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
HEADING = re.compile(r"^# (.+)$", re.M)
# markdown2 slows down quadratically on long Markdown and on long runs of one punctuation mark.
MAX_MARKDOWN_SIZE = 50 * 1024
REPEATED_PUNCTUATION = re.compile(r"([^\w\s]|_)\1{9,}")
BLOCK_TAGS = (
	"address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure",
	"footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
	"section", "table", "td", "th", "tr", "ul",
)  # fmt: skip
LINE_BREAK, KEPT_SPACE = "\x00", "\x01"
WHITESPACE = re.compile(r"\s+")
TEXT_NODES = (NavigableString, CData)
# nh3 slows down quadratically with nesting depth; real pages stay far below this.
MAX_DEPTH = 100
# Links read and made absolute per page, so a page of short relative links cannot grow without bound.
MAX_LINKS = 1000
# Another site's markup: no styles, classes or ids that could restyle or clobber the page it is shown in.
PAGE_CLEANER = nh3.Cleaner(
	tags=(acceptable_elements | mathml_elements).difference(DISALLOWED_TAGS),
	attributes={
		"*": acceptable_attributes.difference(
			{"style", "class", "id", "name", "ping", "background", "longdesc", "poster"}
		)
	},
)


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
	change_status: str | None = None

	@property
	def ok(self) -> bool:
		return self.error is None

	@cached_property
	def content_hash(self) -> str | None:
		"""Changes only when the page's main content changes."""
		return get_content_hash(self.text) if self.ok else None

	def compare(self, previous_hash: str | None):
		"""Sets `change_status` to New, Changed or Unchanged against an earlier crawl's hash."""
		if not self.ok:
			return
		if not previous_hash:
			self.change_status = "New"
		else:
			self.change_status = "Unchanged" if previous_hash == self.content_hash else "Changed"

	@cached_property
	def markdown(self) -> str:
		"""The page as Markdown, converted from the sanitized `html`."""
		return to_markdown(self.html)


class PageParser:
	"""Turns a download into a Crawled Page: main content, text, title, meta tags and links."""

	def __init__(self, download: Download):
		self.download = download

	def parse(self) -> CrawledPage:
		"""Never raises: markup nested too deep for a parser fails this page only."""
		try:
			return self.read()
		except RecursionError:
			return self.failed("failed")

	def read(self) -> CrawledPage:
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
		if len(self.download.content) > MAX_MARKDOWN_SIZE:
			return self.failed("too_large")
		front_matter, markdown = split_front_matter(self.download.text)
		heading = HEADING.search(markdown)
		title = (front_matter.get("title") or (heading[1] if heading else "")).strip()
		html = md_to_html(REPEATED_PUNCTUATION.sub(lambda match: match[1] * 10, markdown))
		soup = BeautifulSoup(html or "", "html.parser")
		return self.build(
			title=title,
			description=front_matter.get("description", ""),
			meta={},
			main=self.main_content(soup),
			raw_html="",
			links=self.links(soup),
		)

	def build(self, title, description, meta, main, raw_html, links) -> CrawledPage:
		text = plain_text(main)
		return CrawledPage(
			url=self.download.url,
			final_url=self.download.final_url,
			status=self.download.status,
			error=None if text else "empty",
			title=title,
			description=description.strip(),
			meta=meta,
			html=PAGE_CLEANER.clean(self.absolute_links(prune_deep(main))),
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
		"""Absolute link URLs and their anchor text, in page order, at most MAX_LINKS."""
		links = {}
		for anchor in soup.find_all("a", href=True, limit=MAX_LINKS):
			if url := absolute_url(self.download.final_url, anchor["href"]):
				links.setdefault(url, anchor.get_text(" ", strip=True))
		return links

	def absolute_links(self, main: Tag) -> str:
		"""`main` with its first MAX_LINKS links made absolute, and the rest and malformed ones removed."""
		for count, tag in enumerate(main.select("a[href], img[src]")):
			attribute = "href" if tag.name == "a" else "src"
			if tag[attribute].startswith("#"):
				continue
			if count < MAX_LINKS and (url := absolute_url(self.download.final_url, tag[attribute])):
				tag[attribute] = url
			else:
				del tag[attribute]
		return str(main)

	def failed(self, error: str) -> CrawledPage:
		return CrawledPage(self.download.url, self.download.final_url, self.download.status, error)


def plain_text(element: Tag) -> str:
	"""The visible text, a line per block element, keeping the spacing of preformatted text.
	One walk with a stack, so deeply nested markup costs neither quadratic time nor recursion."""
	parts, stack = [], [(element, False)]
	while stack:
		node, in_pre = stack.pop()
		if isinstance(node, Tag):
			in_pre = in_pre or node.name == "pre"
			edge = [(LINE_BREAK, in_pre)] if node.name in BLOCK_TAGS else []
			stack += edge + [(child, in_pre) for child in reversed(node.contents)] + edge
		elif node is LINE_BREAK:
			parts.append(LINE_BREAK)
		elif type(node) in TEXT_NODES:
			parts.append(node.replace("\n", LINE_BREAK).replace(" ", KEPT_SPACE) if in_pre else node)
	text = WHITESPACE.sub(" ", "".join(parts))
	lines = (line.strip().replace(KEPT_SPACE, " ") for line in text.split(LINE_BREAK))
	return "\n".join(line for line in lines if line)


def prune_deep(element: Tag) -> Tag:
	"""`element` without the tags nested deeper than MAX_DEPTH. Call it after reading the text."""
	deep, stack = [], [(element, 0)]
	while stack:
		node, depth = stack.pop()
		if depth == MAX_DEPTH:
			deep += [child for child in node.contents if isinstance(child, Tag)]
		else:
			stack += [(child, depth + 1) for child in node.contents if isinstance(child, Tag)]
	for tag in deep:
		tag.decompose()
	return element


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
	"""The scalar values of a Markdown page's YAML front matter as text, and the page without it.
	Lists and mappings are dropped: turning a list of aliases into text can expand a few hundred bytes
	into gigabytes."""
	match = FRONT_MATTER.match(text)
	if not match:
		return {}, text
	try:
		front_matter = yaml.safe_load(match[1])
	except (yaml.YAMLError, RecursionError):
		front_matter = None
	if not isinstance(front_matter, dict):
		front_matter = {}
	scalars = {
		key: str(value) for key, value in front_matter.items() if isinstance(value, str | int | float | date)
	}
	return scalars, text[match.end() :]
