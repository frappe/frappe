# The renderer that turns a URL under /apps into the shell document.

# A built-in ahead of every other renderer, not a `page_renderer` hook: the hook swallows import
# errors, so a typo here would silently drop every /apps URL to a 404.

import os
import re
from html import escape

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.permissions import guard_prefix
from frappe.shell.registry import resolve_prefix, split_shell_path
from frappe.shell.route_guard import is_reserved
from frappe.shell.titles import tab_icon
from frappe.utils.data import is_desk_v2_enabled
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.page_renderers.redirect_page import RedirectPage

#: Vite's output, under the Python package: `/assets/frappe/` is a symlink to `frappe/public/`.
SHELL_DOCUMENT = "public/frontend/index.html"

_ICON_LINK = re.compile(r'(<link rel="icon" href=")[^"]*(")')

_document_cache: dict[str, tuple[float, str]] = {}


def get_shell_document() -> str | None:
	"""The one built document, or None if the shell has not been built."""
	# Read, not rendered: the document carries no per-request content at all.
	path = os.path.join(frappe.get_app_path("frappe"), SHELL_DOCUMENT)
	try:
		mtime = os.path.getmtime(path)
	except OSError:
		return None

	cached = _document_cache.get(path)
	if cached and cached[0] == mtime:
		return cached[1]

	# Constant path, never request-derived.
	with open(path) as f:  # nosemgrep
		document = f.read()

	_document_cache[path] = (mtime, document)
	return document


class ShellPage(BaseRenderer):
	def __init__(self, path, http_status_code=None):
		super().__init__(path, http_status_code)
		self.is_index = self.path == SHELL_ROOT
		self.reserved = is_reserved(self.path)
		self.prefix = None
		self.app = None

		if split := split_shell_path(self.path):
			self.prefix = split[0]
			self.app = resolve_prefix(self.prefix)

	def can_render(self):
		"""True for `/apps` and for every path under a claimed prefix; an unclaimed one is a website 404."""
		return self.is_index or (bool(self.app) and is_desk_v2_enabled())

	def render(self):
		if not is_desk_v2_enabled():
			# 302, not 301: a browser would keep a permanent redirect after desk v2 is turned on.
			frappe.flags.redirect_location = "/desk"
			return RedirectPage(self.path, 302).render()

		# Never cached: `can_cache()` ignores the session user, so a cached shell would hand one
		# user's document to the next. Invisible in development, where `can_cache()` is False.
		frappe.local.no_cache = 1

		# The index is frappe's: its boot is gated on frappe, so the document must be too.
		guard_prefix(self.app or "frappe", self.request_path())

		document = get_shell_document()
		if document is None:
			frappe.throw(
				frappe._("The desk shell has not been built. Run {0}.").format("<code>bench build</code>"),
				title=frappe._("Shell Not Built"),
			)

		# Always 200: a 404 would cost the page its asset preloads, and the miss is the router's to report.
		return self.build_response(self.with_tab_icon(document), 200)

	def with_tab_icon(self, document: str):
		"""The memoized document with this prefix's icon, so the tab is right before any JS runs."""
		# A function, not a string: the href may hold backslashes that `re.sub` would read as groups.
		href = escape(tab_icon(self.app), quote=True)
		return _ICON_LINK.sub(lambda match: f"{match[1]}{href}{match[2]}", document, count=1)

	def request_path(self):
		if frappe.local.request:
			return frappe.local.request.path
		return f"/{self.path}"
