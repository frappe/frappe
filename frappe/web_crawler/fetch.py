import socket
import threading
import time
from concurrent.futures import Future
from contextlib import suppress
from dataclasses import dataclass
from email.message import Message
from functools import cache
from urllib.parse import urljoin

import requests
from requests.utils import requote_uri
from urllib3.exceptions import HTTPError, ReadTimeoutError
from urllib3.util.retry import Retry

from frappe.web_crawler.limits import CrawlLimits

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
	"""Retry that honours Retry-After, but never waits longer than `max_wait` seconds."""

	def __init__(self, *args, max_wait: float = 0, **kwargs):
		super().__init__(*args, **kwargs)
		self.max_wait = max_wait

	def new(self, **kwargs) -> "CappedRetry":
		return super().new(max_wait=self.max_wait, **kwargs)

	def get_retry_after(self, response):
		retry_after = super().get_retry_after(response)
		return None if retry_after is None else min(retry_after, self.max_wait)


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
	"""GETs URLs through the SSRF-guarded session within the crawl's size and time limits."""

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
			total=self.limits.max_retries,
			backoff_factor=0.5,
			status_forcelist=RETRY_STATUSES,
			raise_on_status=False,
			max_wait=self.limits.max_wait,
		)
		for adapter in set(session.adapters.values()):
			adapter.max_retries = retry
			pools = adapter.poolmanager.pool_classes_by_scheme
			adapter.poolmanager.pool_classes_by_scheme = {
				scheme: abortable_pool(pool) for scheme, pool in pools.items()
			}
		session.hooks["response"].append(self.refuse_blocked_redirect)
		return session

	def refuse_blocked_redirect(self, response: requests.Response, **kwargs):
		if not response.is_redirect:
			return
		# requests requotes a redirect target before it parses it, so the check reads the same host.
		if self.limits.is_blocked(requote_uri(urljoin(response.url, response.headers["Location"]))):
			response.close()
			raise FetchError("blocked", response.status_code, response.url)

	def get(self, url: str, max_bytes: int, timeout: float) -> Download:
		"""The body of `url`, within `timeout` seconds per attempt and the crawl's deadline. Raises FetchError."""
		if self.limits.is_blocked(url):
			raise FetchError("blocked")
		allowed = self.limits.request_seconds(timeout)
		if self.deadline:
			allowed = min(allowed, self.deadline - time.monotonic())
		if allowed <= 0:
			raise FetchError(TIME_LIMIT)
		try:
			return AbortableCall().run(self.download, allowed, url, max_bytes, timeout)
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


class AbortableCall:
	"""`function(*args)` in a thread; on timeout, shuts its sockets so the thread ends."""

	active = threading.local()

	def __init__(self):
		self.lock = threading.Lock()
		self.aborted = False
		self.connections = set()

	@classmethod
	def current(cls) -> "AbortableCall":
		return cls.active.call

	def run(self, function, seconds: float, *args):
		future = Future()

		def target():
			self.active.call = self
			try:
				future.set_result(function(*args))
			except BaseException as e:
				future.set_exception(e)

		threading.Thread(target=target, daemon=True).start()
		try:
			return future.result(timeout=seconds)
		except TimeoutError:
			self.abort()
			raise

	def track(self, connection):
		with self.lock:
			if self.aborted:
				connection.close()
			self.check()
			self.connections.add(connection)

	def release(self, connection):
		with self.lock:
			self.connections.discard(connection)

	def check(self):
		if self.aborted:
			raise FetchError("timed_out")

	def abort(self):
		with self.lock:
			self.aborted = True
			for connection in self.connections:
				if not connection.sock:
					continue
				# socket.socket's shutdown, as SSLSocket's would touch TLS state the reading thread owns.
				with suppress(OSError):
					socket.socket.shutdown(connection.sock, socket.SHUT_RDWR)


@cache
def abortable_pool(base: type) -> type:
	"""`base` connection pool, with its connections tracked by the AbortableCall that uses them."""

	class Connection(base.ConnectionCls):
		def connect(self):
			super().connect()
			AbortableCall.current().check()

	class Pool(base):
		ConnectionCls = Connection

		def _get_conn(self, timeout=None):
			connection = super()._get_conn(timeout)
			AbortableCall.current().track(connection)
			return connection

		def _put_conn(self, connection):
			AbortableCall.current().release(connection)
			super()._put_conn(connection)

	return Pool


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
