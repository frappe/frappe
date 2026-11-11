import frappe


def execute():
	"""Helpdesk's `Tag-color` Custom Field becomes the standard `color` field.

	Only the Custom Field record goes: its column and stored values stay, and the options are the same.
	"""
	frappe.db.delete("Custom Field", {"dt": "Tag", "fieldname": "color"})
	frappe.clear_cache(doctype="Tag")
