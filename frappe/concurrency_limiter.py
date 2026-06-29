# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
Concurrency limiter for expensive whitelisted methods.

Provides a @frappe.concurrent_limit() decorator that limits the number of
simultaneous in-flight executions of a function across all gunicorn workers
using a Redis-backed semaphore (LIST + BLPOP).

Usage::

    @frappe.whitelist(allow_guest=True)
    @frappe.concurrent_limit(limit=3)
    def download_pdf(...):
        ...

"""

from collections.abc import Callable
from functools import wraps

import frappe
from frappe.exceptions import ServiceUnavailableError
from frappe.utils import cint
from frappe.utils.caching import redis_cache
from frappe.utils.redis_semaphore import RedisSemaphore

# Default wait timeout (seconds) before returning 503 to the caller.
_DEFAULT_WAIT_TIMEOUT = 10


@redis_cache(shared=True)
def _default_limit() -> int:
	"""Derive a sensible default concurrency limit from gunicorn's max concurrency."""
	return max(1, gunicorn_max_concurrency() // 2)


def gunicorn_max_concurrency() -> int:
	"""Detect max concurrent requests from the running gunicorn master's cmdline."""
	import os

	fallback = 4

	try:
		ppid = os.getppid()
		with open(f"/proc/{ppid}/cmdline", "rb") as f:
			args = f.read().rstrip(b"\0").decode().split("\0")

		if not any("gunicorn" in a for a in args):
			return fallback

		workers = _extract_cli_int(args, "-w", "--workers") or fallback
		threads = _extract_cli_int(args, "--threads") or 1
		return workers * threads
	except OSError:
		return fallback


def _extract_cli_int(args: list[str], *flags: str) -> int | None:
	"""Return the integer value for a CLI flag from a split argument list.

	Handles both ``--flag value`` and ``--flag=value`` forms.
	"""
	for i, arg in enumerate(args):
		for flag in flags:
			if arg == flag and i + 1 < len(args):
				return int(args[i + 1])
			if arg.startswith(f"{flag}="):
				return int(arg.split("=", 1)[1])
	return None


def concurrent_limit(limit: int | None = None, wait_timeout: int = _DEFAULT_WAIT_TIMEOUT):
	"""Decorator that limits simultaneous in-flight executions of the wrapped function.

	:param limit: Maximum number of concurrent executions. Defaults to half of ``workers x threads``
	    as detected from the gunicorn master process.
	:param wait_timeout: Seconds to wait for a free slot before returning 503.
	    Defaults to 10 s.

	The limiter is skipped entirely for background jobs, CLI commands, and
	tests that call functions directly (i.e. outside of an HTTP request).
	"""

	def decorator(fn: Callable) -> Callable:
		@wraps(fn)
		def wrapper(*args, **kwargs):
			# Skip concurrency limiting outside of HTTP requests (background jobs,
			# CLI commands, tests that call functions directly, etc.).
			if getattr(frappe.local, "request", None) is None:
				return fn(*args, **kwargs)

			_limit = cint(limit) if limit is not None else _default_limit()
			key = f"concurrency:{fn.__module__}.{fn.__qualname__}"

			sem = RedisSemaphore(key, _limit, wait_timeout, shared=True)
			token = sem.acquire()
			if not token:
				retry_after = max(1, int(wait_timeout))
				if (headers := getattr(frappe.local, "response_headers", None)) is not None:
					headers.set("Retry-After", str(retry_after))
				exc = ServiceUnavailableError(frappe._("Server is busy. Please try again in a few seconds."))
				exc.retry_after = retry_after
				raise exc

			try:
				return fn(*args, **kwargs)
			finally:
				sem.release(token)

		return wrapper

	return decorator


@frappe.whitelist()
def get_stats() -> dict:
	frappe.only_for("System Manager")
	cached_limit = _default_limit()
	gunicorn_limit = gunicorn_max_concurrency()
	return {
		"cached_limit": cached_limit,
		"gunicorn_limit": gunicorn_limit,
	}
