"""Fieldtype groups the print format builder and its renderers agree on.
Mirrors frappe/public/js/print_format_builder/fieldtypes.js."""

import frappe.utils

IMAGE_FIELDTYPES = frozenset({"Attach Image", "Image", "Attach"})
MERGE_IMAGE_FIELDTYPES = frozenset({"Attach Image", "Attach"})


def is_image_column(fieldtype: str | None, src) -> bool:
	"""A column prints as an image when its type says so, or when a plain Attach holds one."""
	if fieldtype in ("Attach Image", "Image"):
		return True
	return fieldtype == "Attach" and frappe.utils.is_image(str(src or ""))
