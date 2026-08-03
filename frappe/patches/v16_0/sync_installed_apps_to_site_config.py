import frappe
from frappe.installer import update_site_config


def execute():
	"""Backfill installed_apps into site_config.json for existing sites.

	bench-cli (and other tools) can read the list without a DB round-trip by
	checking site_config.json first.  Going forward, install_app / remove_app
	keep this key in sync automatically.
	"""
	update_site_config("installed_apps", frappe.get_installed_apps())
