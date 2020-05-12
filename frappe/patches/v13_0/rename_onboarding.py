# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if frappe.db.exists("DocType", "Onboarding"):
		frappe.rename_doc("DocType", "Onboarding", "Module Onboarding", ignore_if_exists=True)

