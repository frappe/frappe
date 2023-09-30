# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _


def get_context():
	_apps = frappe.get_installed_apps()
	app_shortcuts = [
		{
			"name": "frappe",
			"icon_url": "/assets/frappe/images/frappe-framework-logo.svg",
			"title": _("Admin"),
			"route": "/app",
		}
	]
	for app in _apps:
		app_icon_url = frappe.get_hooks("app_icon_url", app_name=app)
		app_icon_route = frappe.get_hooks("app_icon_route", app_name=app)
		if app_icon_url and app_icon_route:
			app_title = frappe.get_hooks("app_title", app_name=app)
			icon_title = frappe.get_hooks("app_icon_title", app_name=app)
			app_shortcuts.append(
				{
					"name": app,
					"icon_url": app_icon_url[0],
					"title": _(icon_title[0] if icon_title else app_title[0] if app_title else app),
					"route": app_icon_route[0],
				}
			)
	app_shortcuts.append(
		{
			"icon_url": "/assets/frappe/images/my-settings.svg",
			"title": _("Users"),
			"route": "/app/user",
		}
	)
	return {"apps": app_shortcuts}
