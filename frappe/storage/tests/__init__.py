# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Shared helpers for storage v2 tests."""

import frappe


def reset_file_controller():
	"""Drop the cached File controller for the current site.

	``File.resolve_controller`` picks FileV1 or FileV2 from the
	``storage_v2`` flag, and ``get_controller`` caches the result per site.
	A test that toggles the flag must invalidate that cache on the way in
	and on the way out."""
	frappe.controllers.get(frappe.local.site, {}).pop("File", None)
