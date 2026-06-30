# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Handler registry + the realtime.on decorator.

App authors register handlers declaratively::

    from frappe.realtime import Socket, realtime


    @realtime.on("doc_subscribe", frappe_context=True)
    def doc_subscribe(socket: Socket, doctype: str, docname: str) -> None: ...

Each registration stores the callable, its frappe_context / allow_guest flags, and
the owning app. Several apps may bind the same event; dispatch (task 9) runs each
handler only if its app is installed on the connecting site. The owning app is
taken from importing_app(), which the per-app discovery step wraps each import in;
core handlers default to "frappe".
"""

import logging
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger("frappe.realtime")

CORE_APP = "frappe"


@dataclass(frozen=True)
class Handler:
	event: str
	fn: Callable
	frappe_context: bool
	allow_guest: bool
	app: str


class Registry:
	def __init__(self):
		self._handlers: dict[str, list[Handler]] = {}
		self._current_app = CORE_APP

	def on(self, event: str, *, frappe_context: bool = False, allow_guest: bool = False):
		"""Register a handler for an event. Returns the function unchanged."""

		def decorator(fn: Callable) -> Callable:
			handler = Handler(
				event=event,
				fn=fn,
				frappe_context=frappe_context,
				allow_guest=allow_guest,
				app=self._current_app,
			)
			self._handlers.setdefault(event, []).append(handler)
			return fn

		return decorator

	@contextmanager
	def importing_app(self, app: str):
		"""Tag handlers registered inside this block as owned by ``app``."""
		previous = self._current_app
		self._current_app = app
		try:
			yield
		finally:
			self._current_app = previous

	def handlers_for(self, event: str) -> list[Handler]:
		return self._handlers.get(event, [])

	def events(self) -> Iterable[str]:
		return self._handlers.keys()


realtime = Registry()


def discover_app_handlers(sites_path: str | None = None) -> None:
	"""Import ``<app>/realtime/handlers.py`` for every installed app, tagged by app.

	Missing handler modules are ignored. An import error inside an existing handler
	module is NOT swallowed — it surfaces loudly at startup (matches the design).
	Core handlers (frappe.realtime.handlers) are imported separately, so the
	frappe app is skipped here."""
	import importlib
	import importlib.util

	import frappe

	sites_path = sites_path or getattr(frappe.local, "sites_path", None) or "sites"
	for app in frappe.get_all_apps(with_internal_apps=False, sites_path=sites_path):
		if app == CORE_APP:
			continue
		module = f"{app}.realtime.handlers"
		try:
			spec = importlib.util.find_spec(module)
		except ModuleNotFoundError:
			spec = None
		if spec is None:
			continue
		with realtime.importing_app(app):
			importlib.import_module(module)
		logger.info("loaded realtime handlers from %s", module)
