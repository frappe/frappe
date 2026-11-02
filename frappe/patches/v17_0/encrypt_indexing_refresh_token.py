# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils.password import set_encrypted_password


def execute():
	"""Move the Google indexing refresh token from the plain Data field into the Password field."""
	token = frappe.db.get_single_value("Website Settings", "indexing_refresh_token")
	if not token:
		return

	set_encrypted_password("Website Settings", "Website Settings", token, "indexing_refresh_token_secret")
	frappe.db.set_single_value(
		"Website Settings",
		{"indexing_refresh_token_secret": "*" * len(token), "indexing_refresh_token": None},
		update_modified=False,
	)
