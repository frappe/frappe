# The shell hooks a session runs: each app's `<module>/frontend/shell.js`, behind the app's own gate.

import glob

import frappe

from .manifest import shell_hook_glob
from .permissions import has_app_permission, passes_apps_screen_check
from .titles import app_screen

CACHE_KEY = "shell_hook_apps"


def shell_hooks(app_order: list[str]) -> list[dict]:
	"""`{app, title}` for the apps of `app_order`, in that order, that ship a hook this session may run."""
	# Uncached in developer mode, where a new `shell.js` reaches the bundle with no migrate.
	if frappe.conf.developer_mode:
		hooked = hooked_apps()
	else:
		hooked = frappe.client_cache.get_value(CACHE_KEY, generator=hooked_apps)
	hooks = []
	for app in app_order:
		if app not in hooked:
			continue
		screen = (frappe.get_hooks("add_to_apps_screen", app_name=app) or [{}])[0]
		if may_run(app, screen):
			hooks.append({"app": app, "title": app_screen(app, screen)["title"]})
	return hooks


def hooked_apps() -> list[str]:
	"""The installed apps that ship a `shell.js`; the bundle is built from the same path."""
	return [
		app
		for app in frappe.get_installed_apps(_ensure_on_bench=True)
		if glob.glob(shell_hook_glob(frappe.get_app_path(app)))
	]


def may_run(app: str, screen: dict) -> bool:
	"""The app's `add_to_apps_screen` `has_permission`, else its prefix gate."""
	check = screen.get("has_permission")
	return passes_apps_screen_check(app, check) if check else has_app_permission(app)
