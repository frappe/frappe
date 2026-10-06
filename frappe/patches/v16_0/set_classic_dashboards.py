# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	"""Keep upgrading sites on the classic dashboards their users know.

	A fresh install stores the field's default, Insights, and skips this patch. An upgrading site
	has no value, so this patch writes one. A site that has not finished the setup wizard has no
	users yet, such as a standby site waiting for a signup, so it gets Insights like a fresh install.
	An upgraded site switches from System Settings.
	"""
	frappe.db.set_single_value(
		"System Settings", "dashboards", "Classic" if frappe.is_setup_complete() else "Insights"
	)
