# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils.password import set_encrypted_password


def execute():
	"""Move the Google indexing refresh token from the Singles table into __Auth."""
	token = frappe.db.get_single_value("Website Settings", "indexing_refresh_token")
	if not token or set(token) == {"*"}:
		return

	set_encrypted_password("Website Settings", "Website Settings", token, "indexing_refresh_token")
	frappe.db.set_single_value(
		"Website Settings", "indexing_refresh_token", "*" * len(token), update_modified=False
	)
