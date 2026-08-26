# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import re

import orjson

import frappe
from frappe import _
from frappe.core.doctype.installed_applications.installed_applications import (
	get_apps_with_incomplete_dependencies,
	get_setup_wizard_completed_apps,
	get_setup_wizard_not_required_apps,
)
from frappe.utils.caching import request_cache

# check if route is /desk or /desk/* and not /app1 or /app1/*
DESK_APP_PATTERN = re.compile(r"^/desk(/.*)?$")


@request_cache
def get_docked_apps() -> set[str]:
	"""Apps that surface their workspaces inside another app's workspace dock.

	A companion app (e.g. India Compliance for ERPNext) pins its workspaces into a host app's dock
	via the `add_to_workspace_dock` hook instead of taking an apps-screen slot of its own. It is
	kept off the apps screen even when it also declares `add_to_apps_screen` -- companion apps keep
	that hook so they still appear on older versions, so here the dock hook wins."""
	from frappe.boot import get_app_rail_host_map

	return set(get_app_rail_host_map())


@frappe.whitelist()
@request_cache
def get_apps():
	apps = frappe.get_active_apps()
	docked_apps = get_docked_apps()

	app_list = []
	for app in apps:
		if (
			app not in get_setup_wizard_completed_apps()
			and app not in get_setup_wizard_not_required_apps()
			and "System Manager" not in frappe.get_roles()
		):
			continue

		if app == "frappe":
			continue

		if app in docked_apps:
			continue

		app_details = frappe.get_hooks("add_to_apps_screen", app_name=app)
		if not len(app_details):
			continue
		for app_detail in app_details:
			try:
				has_permission_path = app_detail.get("has_permission")
				if has_permission_path and not frappe.get_attr(has_permission_path)():
					continue
				app_list.append(
					{
						"name": app,
						"logo": app_detail.get("logo"),
						"title": _(app_detail.get("title")),
						"route": app_detail.get("route"),
					}
				)
			except Exception:
				frappe.log_error(f"Failed to call has_permission hook ({has_permission_path}) for {app}")
	return app_list


def get_route(app_name):
	# `/desk` rather than `/apps`, because `/apps` used to be a redirect *to* `/desk`
	# and is now the v2 index. These are involuntary destinations — login, default app
	# — so they keep landing exactly where they landed before (#42124).
	if app_name not in frappe.get_active_apps():
		return "/desk"  # Invalid defaults
	apps = frappe.get_hooks("add_to_apps_screen", app_name=app_name)
	app = next((app for app in apps if app.get("name") == app_name), None)
	return app.get("route") if app and app.get("route") else "/desk"


def is_desk_apps(apps):
	for app in apps:
		route = app.get("route")
		if route and not re.match(DESK_APP_PATTERN, route):
			return False
	return True


def get_default_path():
	apps = get_apps()
	_apps = [app for app in apps if app.get("name") != "frappe"]

	if len(_apps) == 0:
		return None

	system_default_app = frappe.get_system_settings("default_app")
	user_default_app = frappe.get_cached_value("User", frappe.session.user, "default_app")
	if system_default_app and not user_default_app:
		return get_route(system_default_app)
	elif user_default_app:
		return get_route(user_default_app)

	if len(_apps) == 1:
		return _apps[0].get("route") or "/desk"

	# Both arms of the old `is_desk_apps` branch now answer `/desk`, so the predicate
	# no longer decides anything here. It is left in place for its other caller
	# (#42124); this is the branch it guarded going quiet.
	return "/desk"


@frappe.whitelist()
def set_app_as_default(app_name: str):
	if app_name in get_disabled_apps():
		frappe.throw(_("App {} is disabled on this site").format(frappe.bold(app_name)))

	if app_name not in get_installed_apps():
		frappe.throw(_("App {} is not installed").format(frappe.bold(app_name)))

	if frappe.db.get_value("User", frappe.session.user, "default_app") == app_name:
		frappe.db.set_value("User", frappe.session.user, "default_app", "")
	else:
		frappe.db.set_value("User", frappe.session.user, "default_app", app_name)


@frappe.whitelist()
def get_incomplete_setup_route(current_app: str, app_route: str):
	pending_apps = get_apps_with_incomplete_dependencies(current_app)

	if not pending_apps:
		return app_route

	for app in pending_apps:
		if app == "frappe":
			return "app"

		app_details = frappe.get_hooks("add_to_apps_screen", app_name=app)
		if not app_details:
			continue

		if route := app_details[0].get("route"):
			return route

	return app_route


def get_all_apps(with_internal_apps=True, sites_path=None):
	"""Get list of all apps via `sites/apps.txt`."""
	from frappe.utils import get_file_items

	if not sites_path:
		sites_path = frappe.local.sites_path

	apps = get_file_items(os.path.join(sites_path, "apps.txt"), raise_not_found=True)

	if with_internal_apps:
		for app in get_file_items(os.path.join(frappe.local.site_path, "apps.txt")):
			if app not in apps:
				apps.append(app)

	if "frappe" in apps:
		apps.remove("frappe")
	apps.insert(0, "frappe")

	return apps


@request_cache
def get_installed_apps(*, _ensure_on_bench: bool = False) -> list[str]:
	"""Get list of installed apps in current site."""
	if getattr(frappe.flags, "in_install_db", True):
		return []

	if not frappe.db:
		frappe.connect()

	installed = orjson.loads(frappe.db.get_global("installed_apps") or "[]")

	if _ensure_on_bench:
		all_apps = frappe.cache.get_value("all_apps", get_all_apps)
		installed = [app for app in installed if app in all_apps]

	return installed


@request_cache
def get_disabled_apps() -> list[str]:
	"""Return apps that are installed on current site but logically disabled."""
	if frappe.flags.in_install_db:
		return []

	if not frappe.db:
		frappe.connect()

	return orjson.loads(frappe.db.get_global("disabled_apps") or "[]")


@request_cache
def get_active_apps(*, _ensure_on_bench: bool = False) -> list[str]:
	"""Installed apps excluding those logically disabled on this site."""
	installed = get_installed_apps(_ensure_on_bench=_ensure_on_bench)
	disabled = get_disabled_apps()

	return [app for app in installed if app not in disabled]
