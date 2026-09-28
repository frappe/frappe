# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


@frappe.whitelist(allow_guest=True)
def web_search(query: str, scope: str | None = None, limit: int = 20):
	"""Kept for compatibility; website search has been removed."""
	return []
