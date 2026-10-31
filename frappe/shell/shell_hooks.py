# The shell hooks a session runs: each app's `<module>/frontend/shell.js`, behind the app's own gate.

import glob

import frappe

from .manifest import shell_hook_glob
from .permissions import has_app_permission

CACHE_KEY = "shell_hook_apps"


def shell_hooks(app_order: list[str]) -> list[str]:
	"""The apps of `app_order`, in that order, that ship a shell hook this session may run."""
	hooked = frappe.client_cache.get_value(CACHE_KEY, generator=hooked_apps)
	return [app for app in app_order if app in hooked and may_run(app)]


def hooked_apps() -> list[str]:
	"""Every app on the bench that ships a `shell.js`; the bundle is built from the same path."""
	return [app for app in frappe.get_all_apps() if glob.glob(shell_hook_glob(frappe.get_app_path(app)))]


def may_run(app: str) -> bool:
	"""The app's `add_to_apps_screen` `has_permission`, else its prefix gate; a raising check refuses."""
	screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [None])[0]
	check = screen and screen.get("has_permission")
	if not check:
		return has_app_permission(app)

	try:
		return bool(frappe.get_attr(check)())
	except Exception:
		frappe.log_error(title=f"add_to_apps_screen has_permission failed for {app}")
		return False
