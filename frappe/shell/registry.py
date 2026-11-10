# The {prefix: app} registry — the one lookup that turns a URL into an app.
# Cached, not werkzeug rules: the Map is rebuilt every request and a `<path:>` rule costs 143 µs.

import frappe
from frappe.desk.app_prefix import declared_prefix

from . import SHELL_ROOT

CACHE_KEY = "shell_prefix_registry"


def is_modular(app: str) -> bool:
	"""Whether this app addresses its doctypes through their module."""
	# Fixed per app, not per doctype: `Workflow` is both a module and a doctype, so a mixed
	# shape inside one app could not tell the two-segment form from the three.
	declared = frappe.get_hooks("app_modular", app_name=app)
	return bool(declared and declared[0])


def build_prefix_registry() -> dict[str, str]:
	"""`{prefix: app}` over the apps active on this site."""
	# Active apps, not installed: a disabled app must stop serving its prefix, and one
	# missing from the bench would raise from `get_hooks` on every /apps URL.
	return {declared_prefix(app): app for app in frappe.get_active_apps(_ensure_on_bench=True)}


def get_prefix_registry() -> dict[str, str]:
	return frappe.client_cache.get_value(CACHE_KEY, generator=build_prefix_registry)


def clear_prefix_registry():
	frappe.client_cache.delete_value(CACHE_KEY)


def clear_prefix_registry_for_app(app_name: str | None = None):
	"""`after_app_install` signature: the hook passes the installed app."""
	clear_prefix_registry()


def resolve_prefix(prefix: str) -> str | None:
	"""The app claiming `prefix`, or None: an unclaimed prefix is a website 404, not a shell one."""
	return get_prefix_registry().get(prefix)


def shell_base(prefix: str) -> str:
	"""The router base for a prefix, so the literal `/apps` never appears in JS."""
	return f"/{SHELL_ROOT}/{prefix}"


def split_shell_path(path: str) -> tuple[str, str] | None:
	"""`(prefix, rest)` for a path under /apps, else None; the bare index is not a prefix."""
	path = path.strip("/ ")
	if path == SHELL_ROOT:
		return None
	if not path.startswith(SHELL_ROOT + "/"):
		return None

	remainder = path[len(SHELL_ROOT) + 1 :]
	prefix, _, rest = remainder.partition("/")
	return (prefix, rest) if prefix else None


def prefix_map() -> dict[str, dict]:
	"""`{prefix: {app, modular}}` — the registry as boot ships it, every app at once."""
	return {prefix: {"app": app, "modular": is_modular(app)} for prefix, app in get_prefix_registry().items()}
