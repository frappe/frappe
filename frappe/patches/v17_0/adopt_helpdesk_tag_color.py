import os

import click

import frappe
from frappe.utils import get_file_json


def execute():
	"""Helpdesk's `Tag-color` Custom Field becomes the standard `color` field.

	Only Helpdesk's own field goes (a Select with the standard options): its column and stored
	values stay. Any other `color` Custom Field is the site's own and overrides the standard
	field, so it stays.
	"""
	custom_field = frappe.db.get_value(
		"Custom Field", {"dt": "Tag", "fieldname": "color"}, ["name", "fieldtype", "options"], as_dict=True
	)
	if not custom_field:
		return

	if not is_helpdesk_color_field(custom_field):
		click.secho(
			f"Kept the Custom Field {custom_field.name} ({custom_field.fieldtype}): it is not Helpdesk's "
			"Select, so it keeps overriding the standard Tag color field.",
			fg="yellow",
		)
		return

	frappe.db.delete("Custom Field", custom_field.name)
	frappe.clear_cache(doctype="Tag")


def is_helpdesk_color_field(custom_field):
	return custom_field.fieldtype == "Select" and color_options(custom_field.options) == color_options(
		standard_color_options()
	)


def standard_color_options():
	path = os.path.join(frappe.get_app_path("frappe", "desk", "doctype", "tag"), "tag.json")
	field = next(df for df in get_file_json(path)["fields"] if df["fieldname"] == "color")
	return field["options"]


def color_options(options):
	return {option.strip() for option in (options or "").split("\n") if option.strip()}
