# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import os
import json
from semantic_version import Version
import frappe
from frappe.utils import cstr

def get_change_log(user=None):
	if not user: user = frappe.session.user

	last_known_versions = frappe._dict(json.loads(frappe.db.get_value("User",
		user, "last_known_versions") or "{}"))
	current_versions = get_versions()

	if not last_known_versions:
		update_last_known_versions()
		return []

	change_log = []
	def set_in_change_log(app, opts, change_log):
		from_version = last_known_versions.get(app, {}).get("version") or "0.0.1"
		to_version = opts["version"]

		if from_version != to_version:
			app_change_log = get_change_log_for_app(app, from_version=from_version, to_version=to_version)

			if app_change_log:
				change_log.append({
					"title": opts["title"],
					"description": opts["description"],
					"version": to_version,
					"change_log": app_change_log
				})

	for app, opts in current_versions.items():
		if app != "frappe":
			set_in_change_log(app, opts, change_log)

	if "frappe" in current_versions:
		set_in_change_log("frappe", current_versions["frappe"], change_log)

	return change_log

def get_change_log_for_app(app, from_version, to_version):
	change_log_folder = os.path.join(frappe.get_app_path(app), "change_log")
	if not os.path.exists(change_log_folder):
		return

	from_version = Version(from_version)
	to_version = Version(to_version)
	# remove pre-release part
	to_version.prerelease = None

	major_version_folders = ["v{0}".format(i) for i in xrange(from_version.major, to_version.major + 1)]
	app_change_log = []

	for folder in os.listdir(change_log_folder):
		if folder in major_version_folders:
			for file in os.listdir(os.path.join(change_log_folder, folder)):
				version = Version(os.path.splitext(file)[0][1:].replace("_", "."))

				if from_version < version <= to_version:
					file_path = os.path.join(change_log_folder, folder, file)
					content = frappe.read_file(file_path)
					app_change_log.append([version, content])

	app_change_log = sorted(app_change_log, key=lambda d: d[0], reverse=True)

	# convert version to string and send
	return [[cstr(d[0]), d[1]] for d in app_change_log]

@frappe.whitelist()
def update_last_known_versions():
	frappe.db.set_value("User", frappe.session.user, "last_known_versions",
		json.dumps(get_versions()), update_modified=False)

@frappe.whitelist()
def get_versions():
	"""Get versions of all installed apps.

	Example:

		{
			"frappe": {
				"title": "Frappe Framework",
				"version": "5.0.0"
			}
		}"""
	versions = {}
	for app in frappe.get_installed_apps(sort=True):
		versions[app] = {
			"title": frappe.get_hooks("app_title", app_name=app)[0],
			"description": frappe.get_hooks("app_description", app_name=app)[0]
		}
		try:
			versions[app]["version"] = frappe.get_attr(app + ".__version__")
		except AttributeError:
			versions[app]["version"] = '0.0.1'

	return versions


