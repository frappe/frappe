# The renderer that turns a URL under /apps into the shell document.
#
# It sits ahead of StaticPage in the built-in chain (`path_resolver.py`), so a file at
# `<app>/www/apps/crm.html` can no longer take the prefix — StaticPage never gets asked
# (#42066).
#
# Not unshadowable, though, and the limit is worth stating: `path_resolver.py` puts the
# `page_renderer` HOOK renderers ahead of every built-in, this one included, so an app
# can still claim `/apps/*` that way. Guarding the hook is not this ticket's, and the
# install guard does not cover it.
#
# It is a built-in rather than a `page_renderer` hook on purpose. That hook swallows
# import errors with a `click.echo` (`path_resolver.py:78-96`), so a typo in the
# framework's own shell would silently drop every /apps URL to a 404.

import os

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.permissions import guard_prefix
from frappe.shell.registry import resolve_prefix, split_shell_path
from frappe.website.page_renderers.base_renderer import BaseRenderer

#: Vite's output, under the Python package because `/assets/frappe/` is a symlink to
#: `frappe/public/` and #42069 fixed the asset root at `/assets/frappe/frontend/`.
#: Source and output are different trees; the source lives at the repo root.
SHELL_DOCUMENT = "public/frontend/index.html"

_document_cache: dict[str, tuple[float, str]] = {}


def get_shell_document() -> str | None:
	"""The one built document, or None if the shell has not been built.

	Read from disk rather than rendered, because the document has no per-request
	content at all — no boot island, no CSRF token, no `__FRONTEND_ROUTE__` (#42072).
	Everything that used to be interpolated here is fetched by the client instead.
	"""
	path = os.path.join(frappe.get_app_path("frappe"), SHELL_DOCUMENT)
	try:
		mtime = os.path.getmtime(path)
	except OSError:
		return None

	cached = _document_cache.get(path)
	if cached and cached[0] == mtime:
		return cached[1]

	# Constant path: `get_app_path("frappe")` joined to a module constant. The request
	# path never reaches it, so there is nothing here to traverse.
	with open(path) as f:  # nosemgrep
		document = f.read()

	_document_cache[path] = (mtime, document)
	return document


class ShellPage(BaseRenderer):
	def __init__(self, path, http_status_code=None):
		super().__init__(path, http_status_code)
		self.is_index = self.path == SHELL_ROOT
		self.prefix = None
		self.app = None

		if split := split_shell_path(self.path):
			self.prefix = split[0]
			self.app = resolve_prefix(self.prefix)

	def can_render(self):
		"""True for `/apps` and for every path under a *claimed* prefix.

		An unclaimed prefix is deliberately not ours: `/apps/nonsense` falls through
		to a website 404, because the shell owns error states only *inside* a prefix
		it serves (#42124).
		"""
		return self.is_index or bool(self.app)

	def render(self):
		# The shell is never cached. `@cache_html` is gated on `can_cache()`, which
		# does not consider the session user, so a cached shell would hand one user's
		# document to the next. That is invisible in development because `can_cache()`
		# is False under `developer_mode` — hence the flag the test has to force.
		# Whether this can ever be relaxed is #42111's.
		frappe.local.no_cache = 1

		if self.app:
			guard_prefix(self.app, self.request_path())
		elif frappe.session.user == "Guest":
			# The index is framework-owned and lists what you may open; there is
			# nothing on it for a signed-out user. Per-app filtering does the rest.
			guard_prefix("frappe", self.request_path())

		document = get_shell_document()
		if document is None:
			frappe.throw(
				frappe._("The desk shell has not been built. Run {0}.").format("<code>bench build</code>"),
				title=frappe._("Shell Not Built"),
			)

		# Always 200, including for a path no client-side route matches. A 404 status
		# would cost the page its asset preloads — `build_response` skips
		# `add_preload_for_bundled_assets` at 404 (`website/utils.py:580-581`) — and
		# the miss is the router's to report, not the server's (#42066).
		return self.build_response(document, 200)

	def request_path(self):
		if frappe.local.request:
			return frappe.local.request.path
		return f"/{self.path}"
