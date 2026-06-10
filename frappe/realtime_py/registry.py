# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Handler registry + the realtime.on decorator.

App authors register handlers declaratively::

    from frappe.realtime_py import Socket, realtime

    @realtime.on("doc_subscribe", frappe_context=True)
    def doc_subscribe(socket: Socket, doctype: str, docname: str) -> None:
        ...

Each registration stores the callable, its frappe_context / allow_guest flags, and
the owning app. Several apps may bind the same event; dispatch (task 9) runs each
handler only if its app is installed on the connecting site. The owning app is
taken from importing_app(), which the per-app discovery step wraps each import in;
core handlers default to "frappe".
"""

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass

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
