import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from frappe.web_crawler.fetch import Fetcher, FetchError
from frappe.web_crawler.urls import canonical_host

ASSET_EXTENSIONS = frozenset(
	(
		".7z", ".avi", ".css", ".csv", ".doc", ".docx", ".eot", ".exe", ".gif", ".gz", ".ico",
		".jpeg", ".jpg", ".js", ".json", ".mov", ".mp3", ".mp4", ".otf", ".pdf", ".png", ".ppt",
		".pptx", ".rar", ".rss", ".svg", ".tar", ".ttf", ".wav", ".webm", ".webp", ".woff",
		".woff2", ".xls", ".xlsx", ".xml", ".zip",
	)
)  # fmt: skip
WEB_SCHEMES = ("http", "https")
ROBOTS_MAX_BYTES = 512 * 1024
INDEX_FILE = re.compile(r"/index\.(?:html?|php)$")
TRACKING_PARAMETERS = re.compile(r"^(?:utm_.*|fbclid|gclid|msclkid|mc_cid|mc_eid)$")


def normalize_url(url: str) -> str:
	"""The key that tells two spellings of a page apart. http and https, `www.`, a trailing slash,
	index.html, the fragment, tracking parameters and the order of parameters make no difference."""
	parts = urlsplit(url.strip())
	scheme = "https" if parts.scheme.lower() in WEB_SCHEMES else parts.scheme.lower()
	host = canonical_host(parts.netloc.rsplit("@", 1)[-1]).removeprefix("www.")
	path = INDEX_FILE.sub("", parts.path).rstrip("/") or "/"
	return urlunsplit((scheme, host, path, normalize_query(parts.query), ""))


def normalize_query(query: str) -> str:
	parameters = parse_qsl(query, keep_blank_values=True)
	return urlencode(sorted((key, value) for key, value in parameters if not TRACKING_PARAMETERS.match(key)))


def site_root(url: str) -> str:
	parts = urlsplit(url)
	return f"{parts.scheme}://{parts.netloc}"


def bare_host(url: str) -> str:
	return canonical_host(urlsplit(url).hostname or "").removeprefix("www.")


class Scope:
	"""The pages a crawl may read: the start URL's host (`www.` ignored), under its path."""

	def __init__(self, start_url: str):
		self.host = bare_host(start_url)
		self.path = urlsplit(normalize_url(start_url)).path.rstrip("/")

	def contains(self, url: str) -> bool:
		parts = urlsplit(url)
		segments = unquote(parts.path).split("/")
		return (
			parts.scheme in WEB_SCHEMES
			and bare_host(url) == self.host
			and (parts.path.rstrip("/") == self.path or parts.path.startswith(f"{self.path}/"))
			and not any(segment in (".", "..") for segment in segments)
		)


class SkipRules:
	"""URLs never worth fetching: non-web schemes, asset files and the caller's patterns."""

	def __init__(self, patterns=()):
		self.patterns = [pattern_parts(pattern) for pattern in patterns]

	def skips(self, url: str) -> bool:
		parts = urlsplit(url)
		path = parts.path.lower()
		return (
			parts.scheme not in WEB_SCHEMES
			or any(path.endswith(extension) for extension in ASSET_EXTENSIONS)
			or any(contains_in_order(url, parts) for parts in self.patterns)
		)


def pattern_parts(pattern: str) -> tuple[str, ...]:
	"""The literal parts of a skip pattern, where `*` stands for any text."""
	return tuple(part for part in pattern.split("*") if part)


def contains_in_order(url: str, parts: tuple[str, ...]) -> bool:
	"""True when `url` contains each part, in order. Linear in the URL, unlike a regular expression."""
	position = 0
	for part in parts:
		if (position := url.find(part, position)) < 0:
			return False
		position += len(part)
	return True


class Robots:
	"""The site's robots.txt, as RFC 9309 reads it: a missing file (4xx) allows everything,
	an unreachable one (5xx, 429 or no answer) allows nothing."""

	def __init__(self, fetcher: Fetcher, start_url: str):
		self.user_agent = fetcher.limits.user_agent
		self.respected = fetcher.limits.respect_robots_txt
		self.parser = RobotFileParser()
		self.parser.parse(self.read(fetcher, f"{site_root(start_url)}/robots.txt").splitlines())

	def read(self, fetcher: Fetcher, url: str) -> str:
		try:
			return fetcher.get(url, ROBOTS_MAX_BYTES, fetcher.limits.page_timeout).text
		except FetchError as e:
			self.parser.disallow_all = not (e.status and 400 <= e.status < 500 and e.status != 429)
			return ""

	def allows(self, url: str) -> bool:
		return not self.respected or self.parser.can_fetch(self.user_agent, url)

	def crawl_delay(self) -> float | None:
		return self.parser.crawl_delay(self.user_agent) if self.respected else None

	def sitemaps(self) -> list[str]:
		return self.parser.site_maps() or []
