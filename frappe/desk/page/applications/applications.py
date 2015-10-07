# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
import frappe.installer
import frappe.sessions
import requests
import subprocess
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

	contrib = get_contrib_apps()
	contrib = {app:contrib[app] for app in contrib if app not in installed}
	out.update(contrib)
	return out

def get_contrib_apps():
	contrib_apps_url = 'https://raw.githubusercontent.com/frappe/bench/master/install_scripts/contrib-apps.json'
	return requests.get(contrib_apps_url).json()

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
	contrib = get_contrib_apps()
	if name not in contrib:
		raise frappe.ValidationError
	subprocess.check_call([find_executable('bench'), 'get-app', name, contrib[name]['repo_url']], cwd=frappe.utils.get_bench_path())
