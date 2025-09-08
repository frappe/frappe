# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os

import click

import frappe
from frappe.core.doctype.data_import.data_import import export_json, import_doc


def sync_fixtures(app=None):
	"""Import, overwrite fixtures from `[app]/fixtures`"""
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()

	frappe.flags.in_fixtures = True

	for app in apps:
		import_fixtures(app)
		import_custom_scripts(app)

	frappe.flags.in_fixtures = False


def import_fixtures(app):
	fixtures_path = frappe.get_app_path(app, "fixtures")
	if not os.path.exists(fixtures_path):
		return

	fixture_files = sorted(os.listdir(fixtures_path))

	for fname in fixture_files:
		if not fname.endswith(".json"):
			continue

		file_path = frappe.get_app_path(app, "fixtures", fname)
		try:
			import_doc(file_path)
		except (ImportError, frappe.DoesNotExistError) as e:
			# fixture syncing for missing doctypes
			print(f"Skipping fixture syncing from the file {fname}. Reason: {e}")


def import_custom_scripts(app):
	"""Import custom scripts from `[app]/fixtures/custom_scripts`"""
	scripts_folder = frappe.get_app_path(app, "fixtures", "custom_scripts")
	if not os.path.exists(scripts_folder):
		return

	for fname in os.listdir(scripts_folder):
		if not fname.endswith(".js"):
			continue

		click.secho(
			f"Importing Client Script `{fname}` from `{scripts_folder}` is not supported. Convert the client script to fixture.",
			fg="red",
		)


def export_fixtures(app=None):
	"""Export fixtures as JSON to `[app]/fixtures`"""
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()
	for app in apps:
		for fixture in frappe.get_hooks("fixtures", app_name=app):
			filters = None
			or_filters = None
			if isinstance(fixture, dict):
				filters = fixture.get("filters")
				or_filters = fixture.get("or_filters")
				fixture = fixture.get("doctype") or fixture.get("dt")
			print(f"Exporting {fixture} app {app} filters {(filters if filters else or_filters)}")
			if not os.path.exists(frappe.get_app_path(app, "fixtures")):
				os.mkdir(frappe.get_app_path(app, "fixtures"))

			export_json(
				fixture,
				frappe.get_app_path(app, "fixtures", frappe.scrub(fixture) + ".json"),
				filters=filters,
				or_filters=or_filters,
				order_by="idx asc, creation asc",
			)
