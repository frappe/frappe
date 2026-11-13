import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from email.message import Message
from urllib.parse import urljoin

import requests
from urllib3.exceptions import HTTPError, ReadTimeoutError
from urllib3.util.retry import Retry

from frappe.web_crawler.limits import MAX_RETRIES, MAX_WAIT_SECONDS, CrawlLimits

CHUNK_SIZE = 8 * 1024
RETRY_STATUSES = (429, 500, 502, 503, 504)
STATUS_ERRORS = {401: "blocked", 403: "blocked", 404: "not_found", 410: "not_found", 429: "blocked"}
TIME_LIMIT = "time_limit"


class FetchError(Exception):
	"""A request that gave no usable body. `code` is the reason code a Crawled Page carries."""

	def __init__(self, code: str, status: int | None = None, final_url: str | None = None):
		super().__init__(code)
		self.code = code
		self.status = status
		self.final_url = final_url


class CappedRetry(Retry):
	"""Retry that honours Retry-After, but never waits longer than MAX_WAIT_SECONDS."""

	def get_retry_after(self, response):
		retry_after = super().get_retry_after(response)
		return None if retry_after is None else min(retry_after, MAX_WAIT_SECONDS)


@dataclass
class Download:
	url: str
	final_url: str
	status: int
	content_type: str
	charset: str | None
	content: bytes

	@property
	def text(self) -> str:
		return self.content.decode(self.charset or "utf-8", errors="replace")


class Fetcher:
	"""GETs URLs through frappe's SSRF-guarded session, within the crawl's size and time limits.
	Once `deadline` (a `time.monotonic()` value) has passed, every request fails with TIME_LIMIT."""

	def __init__(self, limits: CrawlLimits, deadline: float | None = None):
		self.limits = limits
		self.deadline = deadline
		self.session = self.build_session()

	def build_session(self) -> requests.Session:
		from frappe.utils.safe_exec import get_safe_request_session

		session = get_safe_request_session()
		session.max_redirects = self.limits.max_redirects
		session.headers["User-Agent"] = self.limits.user_agent
		retry = CappedRetry(
			total=MAX_RETRIES, backoff_factor=0.5, status_forcelist=RETRY_STATUSES, raise_on_status=False
		)
		for adapter in session.adapters.values():
			adapter.max_retries = retry
		session.hooks["response"].append(self.refuse_blocked_redirect)
		return session

	def refuse_blocked_redirect(self, response: requests.Response, **kwargs):
		if response.is_redirect and self.limits.is_blocked(
			urljoin(response.url, response.headers["Location"])
		):
			response.close()
			raise FetchError("blocked", response.status_code, response.url)

	def get(self, url: str, max_bytes: int, timeout: float) -> Download:
		"""The body of `url`, within `timeout` seconds per attempt and the crawl's deadline. Raises FetchError."""
		if self.limits.is_blocked(url):
			raise FetchError("blocked")
		allowed = (MAX_RETRIES + 1) * (timeout + MAX_WAIT_SECONDS)
		if self.deadline:
			allowed = min(allowed, self.deadline - time.monotonic())
		if allowed <= 0:
			raise FetchError(TIME_LIMIT)
		try:
			return call_with_deadline(self.download, allowed, url, max_bytes, timeout)
		except TimeoutError:
			past_deadline = self.deadline and time.monotonic() >= self.deadline
			raise FetchError(TIME_LIMIT if past_deadline else "timed_out") from None

	def download(self, url: str, max_bytes: int, timeout: float) -> Download:
		deadline = time.monotonic() + timeout
		response = self.send(url, timeout)
		try:
			return self.read(url, response, deadline, max_bytes)
		finally:
			response.close()

	def send(self, url: str, timeout: float) -> requests.Response:
		from frappe.utils.safe_exec import BlockedRequest

		try:
			return self.session.get(url, stream=True, timeout=timeout)
		except BlockedRequest as e:
			raise FetchError("blocked") from e
		except requests.TooManyRedirects as e:
			raise FetchError("too_many_redirects") from e
		except requests.Timeout as e:
			raise FetchError("timed_out") from e
		except (requests.RequestException, HTTPError, ValueError) as e:
			raise FetchError("failed") from e

	def read(self, url: str, response: requests.Response, deadline: float, max_bytes: int) -> Download:
		status = response.status_code
		if status >= 300:
			raise FetchError(status_error(status), status, response.url)
		header = Message()
		header["content-type"] = response.headers.get("Content-Type", "")
		content = read_capped(response, deadline, max_bytes)
		charset = known_charset(header.get_content_charset())
		return Download(url, response.url, status, header.get_content_type(), charset, content)


def known_charset(charset: str | None) -> str | None:
	"""The charset when Python can decode it, so an unknown one falls back to UTF-8."""
	try:
		return charset and b"a".decode(charset, errors="replace") and charset
	except LookupError:
		return None


def call_with_deadline(function, seconds: float, *args):
	"""`function(*args)`, or TimeoutError after `seconds`. A socket timeout only bounds each read,
	so a server that trickles bytes would otherwise hold the crawl for as long as it likes."""
	# ponytail: the late thread is abandoned, not killed; it ends with its request or the job process.
	future = Future()

	def run():
		try:
			future.set_result(function(*args))
		except BaseException as e:
			future.set_exception(e)

	threading.Thread(target=run, daemon=True).start()
	return future.result(timeout=seconds)


def read_capped(response: requests.Response, deadline: float, max_bytes: int) -> bytes:
	"""The decoded body, one network read at a time, so the deadline is checked between reads."""
	body = bytearray()
	try:
		while chunk := response.raw.read1(CHUNK_SIZE, decode_content=True):
			body += chunk
			if len(body) > max_bytes:
				raise FetchError("too_large", response.status_code, response.url)
			if time.monotonic() > deadline:
				raise FetchError("timed_out", response.status_code, response.url)
	except ReadTimeoutError as e:
		raise FetchError("timed_out", response.status_code, response.url) from e
	except (requests.RequestException, HTTPError) as e:
		raise FetchError("failed", response.status_code, response.url) from e
	return bytes(body)


def status_error(status: int) -> str:
	if status >= 500:
		return "server_error"
	return STATUS_ERRORS.get(status, "failed")
