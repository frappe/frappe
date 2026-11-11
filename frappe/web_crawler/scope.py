import re
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from frappe.web_crawler.fetch import Fetcher, FetchError

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


def normalize_url(url: str) -> str:
	"""One spelling per page: lower-case host, no query or fragment, no trailing slash."""
	parts = urlsplit(url.strip())
	path = parts.path.rstrip("/") or "/"
	return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def site_root(url: str) -> str:
	parts = urlsplit(url)
	return f"{parts.scheme}://{parts.netloc}"


def bare_host(url: str) -> str:
	host = (urlsplit(url).hostname or "").rstrip(".")
	return host.removeprefix("www.")


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
		self.patterns = [compile_pattern(pattern) for pattern in patterns]

	def skips(self, url: str) -> bool:
		parts = urlsplit(url)
		path = parts.path.lower()
		return (
			parts.scheme not in WEB_SCHEMES
			or any(path.endswith(extension) for extension in ASSET_EXTENSIONS)
			or any(pattern.search(url) for pattern in self.patterns)
		)


def compile_pattern(pattern: str) -> re.Pattern:
	"""A regular expression, or a plain substring match when the pattern is not valid regex."""
	try:
		return re.compile(pattern)
	except re.error:
		return re.compile(re.escape(pattern))


class Robots:
	"""The site's robots.txt. A missing or unreadable file allows everything."""

	def __init__(self, fetcher: Fetcher, start_url: str):
		self.user_agent = fetcher.limits.user_agent
		self.respected = fetcher.limits.respect_robots_txt
		self.parser = RobotFileParser()
		self.parser.parse(self.read(fetcher, f"{site_root(start_url)}/robots.txt").splitlines())

	def read(self, fetcher: Fetcher, url: str) -> str:
		try:
			return fetcher.get(url, ROBOTS_MAX_BYTES, fetcher.limits.page_timeout).text
		except FetchError:
			return ""

	def allows(self, url: str) -> bool:
		return not self.respected or self.parser.can_fetch(self.user_agent, url)

	def crawl_delay(self) -> float | None:
		return self.parser.crawl_delay(self.user_agent) if self.respected else None

	def sitemaps(self) -> list[str]:
		return self.parser.site_maps() or []
