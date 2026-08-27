# The {prefix: app} registry — the one lookup that turns a URL into an app.
#
# #42066 chose a cached registry over synthesised werkzeug rules: a `<path:>` rule
# costs a measured 143 µs in `Map.add` and the Map is rebuilt every request, so N apps
# would tax every request on the bench, including the ones that never reach the shell.

import re

import frappe

from . import SHELL_ROOT

#: A prefix is one bare path segment. The format is checked at install rather than
#: documented, because the value reaches a URL and a directory name.
PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

CACHE_KEY = "shell_prefix_registry"


def default_prefix(app: str) -> str:
	"""The prefix an app gets when it declares nothing.

	`frappe_whatsapp` becomes `whatsapp`; underscores are otherwise preserved, so
	`hr_management` stays `hr_management` rather than guessing at a nicer name.
	"""
	prefix = app.removeprefix("frappe_")
	# An app named exactly `frappe_` would strip to nothing. Keep the name instead of
	# claiming the empty prefix, which would swallow the whole of /apps.
	return prefix or app


def declared_prefix(app: str) -> str:
	"""This app's prefix, declared or derived.

	Read with `app_name=` because that path is a plain `importlib` call: it works
	before the app is installed (the install guard needs it) and with no site at all
	(`bench build` runs `frappe.init("")`, #42105).
	"""
	declared = frappe.get_hooks("app_prefix", app_name=app)
	# `app_prefix` is a scalar hook, so `get_hooks` hands back a one-element list.
	# A dict form would be broken here — `append_hook` deep-merges and listifies
	# leaves, losing which app said what (#42065).
	return declared[0] if declared else default_prefix(app)


def build_prefix_registry() -> dict[str, str]:
	"""`{prefix: app}` over the apps active on this site.

	`get_active_apps(_ensure_on_bench=True)` rather than `get_installed_apps()`, for
	the two reasons `_load_app_hooks` uses it: a **disabled** app must not keep serving
	its prefix, and an app still in `installed_apps` but no longer on the bench would
	raise from `get_hooks(app_name=)` — turning one missing directory into a 500 on
	every /apps URL and on every subsequent install.
	"""
	return {declared_prefix(app): app for app in frappe.get_active_apps(_ensure_on_bench=True)}


def get_prefix_registry() -> dict[str, str]:
	return frappe.client_cache.get_value(CACHE_KEY, generator=build_prefix_registry)


def clear_prefix_registry():
	frappe.client_cache.delete_value(CACHE_KEY)


def clear_prefix_registry_for_app(app_name: str | None = None):
	"""`after_app_install` signature — the hook passes the app that was installed."""
	clear_prefix_registry()


def resolve_prefix(prefix: str) -> str | None:
	"""The app claiming `prefix`, or None if nobody claims it.

	Unclaimed is None rather than an error: `/apps/nonsense` is a website 404, not a
	shell 404, because the shell owns error states only *inside* a claimed prefix
	(#42124).
	"""
	return get_prefix_registry().get(prefix)


def shell_base(prefix: str) -> str:
	"""The router base for a prefix — the composed path, not the segment.

	Boot carries this rather than the bare prefix so the literal `/apps` never has to
	appear in JS (#42125).
	"""
	return f"/{SHELL_ROOT}/{prefix}"


def split_shell_path(path: str) -> tuple[str, str] | None:
	"""Split a request path into `(prefix, rest)`, or None if it is not under /apps.

	`apps/crm` -> `("crm", "")`, `apps/crm/deal/CRM-001` -> `("crm", "deal/CRM-001")`,
	`apps` -> None (the index is not a prefix, #42124).
	"""
	path = path.strip("/ ")
	if path == SHELL_ROOT:
		return None
	if not path.startswith(SHELL_ROOT + "/"):
		return None

	remainder = path[len(SHELL_ROOT) + 1 :]
	prefix, _, rest = remainder.partition("/")
	return (prefix, rest) if prefix else None
