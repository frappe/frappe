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

import os
import sys
from collections.abc import Callable
from functools import cache, wraps

import frappe
from frappe.exceptions import ServiceUnavailableError
from frappe.utils import cint
from frappe.utils.redis_semaphore import RedisSemaphore

# Default wait timeout (seconds) before returning 503 to the caller.
_DEFAULT_WAIT_TIMEOUT = 10


@cache
def web_tier_concurrency() -> int | None:
	"""Number of requests this process' web tier serves at once.

	Returns ``None`` when there is no fixed pool to exhaust: the development
	server starts a thread per request, and CLI commands and background jobs
	are not a web tier at all.

	Gunicorn sets ``SERVER_SOFTWARE``, and its workers are forked from the master,
	so ``sys.argv`` in a worker is the master's own command line. Both hold on
	every platform. Reading the parent's ``/proc/<pid>/cmdline`` instead reports
	nothing on macOS, where every process then looks like a small gunicorn.
	"""
	if not os.environ.get("SERVER_SOFTWARE", "").startswith("gunicorn"):
		return None

	workers = _extract_cli_int(sys.argv, "-w", "--workers") or 1
	threads = _extract_cli_int(sys.argv, "--threads") or 1
	return workers * threads


def _default_limit() -> int | None:
	"""Half of the web tier's capacity, or ``None`` when nothing needs protecting."""
	capacity = web_tier_concurrency()
	return max(1, capacity // 2) if capacity else None


def _extract_cli_int(args: list[str], *flags: str) -> int | None:
	"""Return the integer value for a CLI flag from a split argument list.

	Handles both ``--flag value`` and ``--flag=value`` forms.
	"""
	for i, arg in enumerate(args):
		for flag in flags:
			value = None
			if arg == flag and i + 1 < len(args):
				value = args[i + 1]
			elif arg.startswith(f"{flag}="):
				value = arg.split("=", 1)[1]

			if value is not None:
				try:
					return int(value)
				except ValueError:
					return None
	return None


def concurrent_limit(limit: int | None = None, wait_timeout: int = _DEFAULT_WAIT_TIMEOUT):
	"""Decorator that limits simultaneous in-flight executions of the wrapped function.

	:param limit: Maximum number of concurrent executions. Defaults to half of ``workers x threads``
	    as detected from the gunicorn command line, and to no limit when the process serves
	    requests without a fixed worker pool.
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
			if _limit is None:
				return fn(*args, **kwargs)

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
	return {
		"default_limit": _default_limit(),
		"web_tier_concurrency": web_tier_concurrency(),
	}
