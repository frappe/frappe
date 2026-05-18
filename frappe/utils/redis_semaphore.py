# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Distributed counting semaphore backed by a Redis LIST."""

import frappe


class RedisSemaphore:
	"""A distributed counting semaphore backed by a Redis LIST.

	Allows up to *limit* concurrent holders across all processes sharing the
	same Redis instance. The token pool is lazily initialized and self-heals
	after crashes thanks to a TTL on the capacity key.

	Usage as a context manager::

	    sem = RedisSemaphore("my-resource", limit=5, wait_timeout=10)
	    with sem:
	        ...  # at most 5 concurrent holders

	Or acquire/release manually::

	    token = sem.acquire()
	    if token is None:
	        raise Exception("Too busy")
	    try:
	        ...
	    finally:
	        sem.release(token)
	"""

	# Safety TTL (seconds) for the capacity key — allows the pool to self-heal
	# after a worker crash that leaked a token.
	CAPACITY_TTL = 3600  # 1 hour

	def __init__(self, key: str, limit: int, wait_timeout: float = 0, shared: bool = False):
		"""
		:param key: A unique Redis key name for this semaphore (will be
		    prefixed by the cache layer).
		:param limit: Maximum number of concurrent holders.
		:param wait_timeout: Seconds to block waiting for a free slot.
		    0 means non-blocking (immediate return if unavailable).
		:param shared: If True, the semaphore key is bench-wide (not
		    prefixed with the site's db_name). Defaults to site-scoped.
		"""
		self.key = key
		self.limit = limit
		self.wait_timeout = wait_timeout
		self.shared = shared
		self._token: str | None = None

	def acquire(self) -> str | None:
		"""Try to acquire a token from the pool.

		Returns a token string on success, ``None`` if no slot was
		available within *wait_timeout*, or ``"fallback"`` if Redis is
		unreachable (fail-open).
		"""
		try:
			self._ensure_tokens()

			if self.wait_timeout <= 0:
				result = frappe.cache.lpop(self.key, shared=self.shared)
				return self._decode(result) if result is not None else None

			if result := frappe.cache.blpop(self.key, timeout=int(self.wait_timeout), shared=self.shared):
				return self._decode(result[1])
			return None

		except Exception:
			frappe.log_error(f"RedisSemaphore({self.key}): Redis unavailable, skipping limit")
			return "fallback"

	def release(self, token: str) -> None:
		"""Return *token* to the pool."""
		if token == "fallback":
			return
		try:
			frappe.cache.lpush(self.key, token, shared=self.shared)
		except Exception:
			frappe.log_error(f"RedisSemaphore({self.key}): Failed to release token {token}")

	# -- context-manager protocol ------------------------------------------

	def __enter__(self):
		self._token = self.acquire()
		return self._token

	def __exit__(self, *exc_info):
		if self._token is not None:
			self.release(self._token)
			self._token = None

	# -- internals ---------------------------------------------------------

	def _ensure_tokens(self) -> None:
		"""Lazily initialize the token pool."""
		try:
			if frappe.cache.exists(f"{self.key}:capacity", shared=self.shared):
				return
			frappe.cache.set_value(
				f"{self.key}:capacity",
				self.limit,
				expires_in_sec=self.CAPACITY_TTL,
				shared=self.shared,
			)
			frappe.cache.delete_value(self.key, shared=self.shared)
			for i in range(1, self.limit + 1):
				frappe.cache.lpush(self.key, str(i), shared=self.shared)
		except Exception:
			frappe.log_error(f"RedisSemaphore({self.key}): Failed to initialize tokens")

	@staticmethod
	def _decode(result):
		return result.decode() if isinstance(result, bytes) else result
