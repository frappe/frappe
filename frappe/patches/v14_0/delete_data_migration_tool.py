# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe


def execute():
	doctypes = frappe.get_all("DocType", {"module": "Data Migration", "custom": 0}, pluck="name")
	for doctype in doctypes:
		frappe.delete_doc("DocType", doctype, ignore_missing=True)

	frappe.delete_doc("Module Def", "Data Migration", ignore_missing=True, force=True)
