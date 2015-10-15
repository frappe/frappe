# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
import frappe.installer
import frappe.sessions
import subprocess
import os
import json
from frappe import _
from distutils.spawn import find_executable

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

	app_listing = get_app_listing()
	app_listing = {app:app_listing[app] for app in app_listing if app not in installed}
	out.update(app_listing)
	return out

def get_app_listing():
	apps_listing_dir = os.path.join(os.path.dirname(frappe.__file__), 'data', 'app_listing')
	def get_app_path(app, *path):
		return os.path.join(apps_listing_dir, app, *path)
	out = {}
	apps = [app for app in os.listdir(apps_listing_dir)
			if os.path.isdir(get_app_path(app)) and
			os.path.exists(get_app_path(app, 'data.json'))]
	for app in apps:
		with open(get_app_path(app, 'data.json')) as f:
			out[app] = json.load(f)
	return out

@frappe.whitelist()
def install_app(name):
	if name not in frappe.get_all_apps(True):
		get_app(name)
		frappe.cache().delete_value(["app_hooks"])
		# reload sys.path
		import site
		reload(site)
	app_hooks = frappe.get_hooks(app_name=name)
	if app_hooks.get('hide_in_installer'):
		frappe.throw(_("You cannot install this app"))

	frappe.installer.install_app(name)

def get_app(name):
	app_listing = get_app_listing()
	if name not in app_listing:
		raise frappe.ValidationError
	subprocess.check_call([find_executable('bench'), 'get-app', name, app_listing[name]['repo_url']], cwd=frappe.utils.get_bench_path())
