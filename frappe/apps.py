# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

import frappe
from frappe import _


@frappe.whitelist()
def get_apps():
	apps = frappe.get_installed_apps()
	app_list = [
		{
			"name": "frappe",
			"icon_url": "/assets/frappe/images/frappe-framework-logo.svg",
			"title": _("Admin"),
			"route": "/app",
		}
	]
	for app in apps:
		if app == "frappe":
			continue
		app_icon_url = frappe.get_hooks("app_icon_url", app_name=app)
		app_icon_route = frappe.get_hooks("app_icon_route", app_name=app)
		if app_icon_url and app_icon_route:
			app_title = frappe.get_hooks("app_title", app_name=app)
			icon_title = frappe.get_hooks("app_icon_title", app_name=app)
			app_list.append(
				{
					"name": app,
					"icon_url": app_icon_url[0],
					"title": _(icon_title[0] if icon_title else app_title[0] if app_title else app),
					"route": app_icon_route[0],
				}
			)
	return app_list


def get_route(app_name):
	hooks = frappe.get_hooks(app_name=app_name)
	if hooks.get("app_icon_route"):
		return hooks.get("app_icon_route")[0]
	return "/apps"


def is_desk_apps(apps):
	for app in apps:
		# check if route is /app or /app/* and not /app1 or /app1/*
		pattern = r"^/app(/.*)?$"
		route = app.get("route")
		if route and not re.match(pattern, route):
			return False
	return True


def get_default_path():
	system_default_app = frappe.get_system_settings("default_app")
	user_default_app = frappe.db.get_value("User", frappe.session.user, "default_app")
	if system_default_app and not user_default_app:
		return get_route(system_default_app)
	elif user_default_app:
		return get_route(user_default_app)

	apps = get_apps()
	_apps = [app for app in apps if app.get("name") != "frappe"]
	if len(_apps) == 1:
		return _apps[0].get("route") or "/apps"
	elif is_desk_apps(_apps):
		return "/app"
	return "/apps"
