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
	"""Get list of all apps with properties, installed, category from hooks and
	`frappe/data/app_listing/` if an entry exists"""
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

	for app_from_list in get_app_listing().values():
		if app_from_list.app_name in out:
			out[app_from_list.app_name].update(app_from_list)
		else:
			if not frappe.conf.disallow_app_listing:
				out[app_from_list.app_name] = app_from_list

	return out

def get_app_listing():
	"""Get apps listed in `frappe/data/app_listing/`"""
	apps_listing_dir = os.path.join(os.path.dirname(frappe.__file__), 'data', 'app_listing')
	out = {}
	for app in os.listdir(apps_listing_dir):
		if app.endswith(".json"):
			with open(os.path.join(apps_listing_dir, app)) as f:
				out[app] = frappe._dict(json.load(f))
	return out

@frappe.whitelist()
def install_app(name):
	"""Install app, if app is not installed in local environment, install it via git url in
	`frappe/data/app_listing/`"""
	frappe.only_for("System Manager")

	if name not in frappe.get_all_apps(True):
		if not frappe.conf.disallow_app_listing:
			get_app(name)
			frappe.cache().delete_value(["app_hooks"])
			# reload sys.path
			import site
			reload(site)
		else:
			# will only come via direct API
			frappe.throw("Listing app not allowed")

	app_hooks = frappe.get_hooks(app_name=name)
	if app_hooks.get('hide_in_installer'):
		frappe.throw(_("You cannot install this app"))

	frappe.publish_realtime("install_app_progress", {"status": _("Installing App {0}").format(name)},
		user=frappe.session.user, now=True)

	frappe.installer.install_app(name)

	frappe.publish_realtime("install_app_progress", {"status": _("{0} Installed").format(name)},
		user=frappe.session.user, now=True)

def get_app(name):
	"""Get app using git clone and install it in bench environment"""
	app_listing = get_app_listing()
	if name not in app_listing:
		frappe.throw(_("Unknown app"))
		raise frappe.ValidationError

	frappe.publish_realtime("install_app_progress", {"status": _("Downloading App {0}").format(name)},
		user=frappe.session.user, now=True)

	args = [find_executable('bench'), 'get-app', name, app_listing[name]['repo_url']]

	try:
		subprocess.check_call(args, cwd=frappe.utils.get_bench_path(),
			stderr=subprocess.STDOUT)
		return "okay"
	except subprocess.CalledProcessError as e:
		frappe.msgprint("<b>" + " ".join(args) + "</b>")
		frappe.msgprint(e.output)
		return e.output
