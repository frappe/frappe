# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe


def get_context():
	_apps = frappe.get_installed_apps()
	apps = []
	for app in _apps:
		homepage = frappe.get_hooks("app_homepage", app_name=app)
		if homepage:
			app_title = frappe.get_hooks("app_title", app_name=app)
			homepage_title = frappe.get_hooks("app_homepage_title", app_name=app)
			logo = frappe.get_hooks("app_logo_url", app_name=app)
			apps.append(
				{
					"name": app,
					"title": app_title[0] if app_title else app,
					"homepage_title": homepage_title[0] if homepage_title else app,
					"logo_url": logo[0] if logo else None,
					"homepage": homepage[0],
				}
			)
	return {"apps": apps}
