# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	if frappe.db.exists("DocType", "Onboarding"):
		frappe.rename_doc("DocType", "Onboarding", "Module Onboarding", ignore_if_exists=True)
