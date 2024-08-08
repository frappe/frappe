# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


@frappe.whitelist()
def get_apps():
	apps = frappe.get_installed_apps()
	app_list = []
	for app in apps:
		if app == "frappe":
			app_list.append(app)
		else:
			app_icon_url = frappe.get_hooks("app_icon_url", app_name=app)
			app_icon_route = frappe.get_hooks("app_icon_route", app_name=app)
			if app_icon_url and app_icon_route:
				app_list.append(app)
	return app_list


def get_route(app_name):
	hooks = frappe.get_hooks(app_name=app_name)
	if hooks.get("app_icon_route"):
		return hooks.get("app_icon_route")[0]
	return "/apps"


def get_default_path():
	system_default_app = frappe.get_system_settings("default_app")
	user_default_app = frappe.db.get_value("User", frappe.session.user, "default_app")
	if system_default_app and not user_default_app:
		return get_route(system_default_app)
	elif user_default_app:
		return get_route(user_default_app)

	apps = get_apps()
	if len(apps) == 2:
		_apps = [app for app in apps if app != "frappe"]
		first_app = _apps[0]
		if first_app:
			return get_route(first_app)
	return "/apps"
