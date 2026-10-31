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
from typing import NamedTuple

import frappe
from frappe.exceptions import ServiceUnavailableError
from frappe.utils import cint
from frappe.utils.redis_semaphore import RedisSemaphore

# Default wait timeout (seconds) before returning 503 to the caller.
_DEFAULT_WAIT_TIMEOUT = 10


class WebTierSettings(NamedTuple):
	"""Gunicorn's resolved settings for the web tier this process serves.

	``timeout`` is how long a worker may stay silent before the master kills it, not a
	request time limit: ``0`` disables it, and a threaded worker keeps notifying the
	master while its requests run.
	"""

	workers: int
	threads: int
	timeout: int
	graceful_timeout: int


@cache
def web_tier_settings() -> WebTierSettings | None:
	"""Gunicorn settings of the web tier this process serves.

	Returns ``None`` when there is no fixed pool to exhaust: the development
	server starts a thread per request, and CLI commands and background jobs
	are not a web tier at all. Also ``None`` when gunicorn's settings cannot be
	resolved, so that nothing is derived from guessed settings.

	Gunicorn sets ``SERVER_SOFTWARE``, and its workers are forked from the master,
	so ``sys.argv`` and ``os.environ`` in a worker are the master's. Reading the
	parent's ``/proc/<pid>/cmdline`` instead reports nothing on macOS, where every
	process then looks like a small gunicorn.
	"""
	if not os.environ.get("SERVER_SOFTWARE", "").startswith("gunicorn"):
		return None

	try:
		cfg = _gunicorn_config()
	except SystemExit:
		return None
	return WebTierSettings(cfg.workers, cfg.threads, cfg.timeout, cfg.graceful_timeout)


def web_tier_concurrency() -> int | None:
	"""Number of requests this process' web tier serves at once, or ``None`` as in `web_tier_settings`."""
	settings = web_tier_settings()
	return settings.workers * settings.threads if settings else None


def _gunicorn_config():
	"""Resolve gunicorn's settings the way its command line runner does.

	Gunicorn does not pass its config to the application, so this reads the same
	sources in the same order: defaults (including ``WEB_CONCURRENCY``), the config
	file, ``GUNICORN_CMD_ARGS``, then the command line. A worker reuses the config
	module the master loaded instead of running the file again. Gunicorn exits on
	invalid settings, which raises ``SystemExit`` here.
	"""
	from gunicorn.app.base import Application
	from gunicorn.config import get_default_config_file

	class Settings(Application):
		def get_config_from_filename(self, filename):
			if config := sys.modules.get("__config__"):
				return vars(config)
			return super().get_config_from_filename(filename)

		def load_config(self):
			parser = self.cfg.parser()
			args = parser.parse_args(sys.argv[1:])
			env_args = parser.parse_args(self.cfg.get_cmd_args_from_env())

			if config_file := args.config or env_args.config or get_default_config_file():
				self.load_config_from_file(config_file)

			for parsed in (env_args, args):
				for name, value in vars(parsed).items():
					if value is not None and name != "args":
						self.cfg.set(name.lower(), value)

	return Settings().cfg


def _default_limit() -> int | None:
	"""Half of the web tier's capacity, or ``None`` when nothing needs protecting."""
	capacity = web_tier_concurrency()
	return max(1, capacity // 2) if capacity else None


def concurrent_limit(limit: int | None = None, wait_timeout: int = _DEFAULT_WAIT_TIMEOUT):
	"""Decorator that limits simultaneous in-flight executions of the wrapped function.

	:param limit: Maximum number of concurrent executions. Defaults to half of gunicorn's
	    ``workers x threads``, and to no limit when the process serves requests without a fixed
	    worker pool or the pool's size cannot be resolved.
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
				exc.skip_error_log = True
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
