# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

import frappe
from frappe import _
from frappe.boot import get_bootinfo
from frappe.desk.utils import slug


@frappe.whitelist()
def get_apps():
	apps = frappe.get_installed_apps()
	app_list = []
	for app in apps:
		if app == "frappe":
			continue
		app_details = frappe.get_hooks("add_to_apps_screen", app_name=app)
		if not len(app_details):
			continue
		for app_detail in app_details:
			has_permission_path = app_detail.get("has_permission")
			if has_permission_path and not frappe.get_attr(has_permission_path)():
				continue
			app_list.append(
				{
					"name": app,
					"logo": app_detail.get("logo"),
					"title": _(app_detail.get("title")),
					"route": get_route(app),
				}
			)
	return app_list


def get_route(app_name):
	apps = frappe.get_hooks("add_to_apps_screen", app_name=app_name)
	app = next((app for app in apps if app.get("name") == app_name), None)
	route = app.get("route") if app and app.get("route") else "/apps"

	# Check if user has access to default workspace, if not, pick first workspace user has access to
	if route.startswith("/app/"):
		ws = route.split("/")[2]
		bootinfo = get_bootinfo()
		allowed_workspaces = bootinfo.get("allowed_workspaces")
		if not allowed_workspaces:
			return "/app"

		for allowed_ws in allowed_workspaces:
			if allowed_ws.get("name").lower() == ws.lower():
				return route

		module_app = bootinfo.get("module_app")
		for allowed_ws in allowed_workspaces:
			module = allowed_ws.get("module")
			if module and module_app.get(module.lower()) == app_name:
				return f"/app/{slug(allowed_ws.name.lower())}"
		return f"/app/{slug(allowed_workspaces[0].get('name').lower())}"
	else:
		return route


def is_desk_apps(apps):
	for app in apps:
		# check if route is /app or /app/* and not /app1 or /app1/*
		pattern = r"^/app(/.*)?$"
		route = app.get("route")
		if route and not re.match(pattern, route):
			return False
	return True


def get_default_path():
	apps = get_apps()
	_apps = [app for app in apps if app.get("name") != "frappe"]

	if len(_apps) == 0:
		return None

	system_default_app = frappe.get_system_settings("default_app")
	user_default_app = frappe.db.get_value("User", frappe.session.user, "default_app")
	if system_default_app and not user_default_app:
		return get_route(system_default_app)
	elif user_default_app:
		return get_route(user_default_app)

	if len(_apps) == 1:
		return _apps[0].get("route") or "/apps"
	elif is_desk_apps(_apps):
		return "/app"
	return "/apps"


@frappe.whitelist()
def set_app_as_default(app_name):
	if frappe.db.get_value("User", frappe.session.user, "default_app") == app_name:
		frappe.db.set_value("User", frappe.session.user, "default_app", "")
	else:
		frappe.db.set_value("User", frappe.session.user, "default_app", app_name)
