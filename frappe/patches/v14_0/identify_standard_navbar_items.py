import frappe
from frappe.core.doctype.navbar_settings.navbar_settings import (
	STANDARD_HELP_ITEMS,
	STANDARD_NAVBAR_ITEMS,
)


def execute():
	"""To identify and safely update navbar items "id" field was added, this field has no value in exisitng installations.

	Try to guess and populate ID from existing label / type."""

	navbar = frappe.get_doc("Navbar Settings")

	identify_existing_items(STANDARD_NAVBAR_ITEMS, navbar.settings_dropdown)
	identify_existing_items(STANDARD_HELP_ITEMS, navbar.help_dropdown)

	# remove all unknown standard fields to avoid duplicates
	remove_unknown_standard_fields(navbar)
	navbar.save()

	navbar.reload()
	navbar.update_standard_navbar_items()
	navbar.save()


def identify_existing_items(standard_items, existing_items):
	for existing_item in existing_items:
		update_id_field(existing_item, standard_items)


def update_id_field(existing_item, standard_items):
	match_fields = ("item_label", "item_type", "is_standard")

	for standard_item in standard_items:
		if all(standard_item.get(field) == existing_item.get(field) for field in match_fields):
			existing_item.id = standard_item.get("id")
			return


def remove_unknown_standard_fields(navbar):
	entries_to_remove = [
		entry
		for entry in navbar.settings_dropdown + navbar.help_dropdown
		if entry.get("is_standard") and not entry.get("id")
	]
	for entry in entries_to_remove:
		navbar.remove(entry)
