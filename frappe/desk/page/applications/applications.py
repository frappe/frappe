# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.installer
from frappe import _

@frappe.whitelist()
def get_app_list():
	out = {}
	installed = frappe.get_installed_apps()
	for app in frappe.get_all_apps(True):
		app_hooks = frappe.get_hooks(app_name=app)

		if app not in installed and app_hooks.get('hide_in_installer'):
			continue

		out[app] = {}
		for key in ("app_name", "app_title", "app_description", "app_icon",
			"app_publisher", "app_version", "app_url", "app_color"):
			 val = app_hooks.get(key) or []
			 out[app][key] = val[0] if len(val) else ""

		if app in installed:
			out[app]["installed"] = 1

	return out

@frappe.whitelist()
def install_app(name):
	app_hooks = frappe.get_hooks(app_name=name)
	if app_hooks.get('hide_in_installer'):
		frappe.throw(_("You cannot install this app"))

	frappe.installer.install_app(name)
