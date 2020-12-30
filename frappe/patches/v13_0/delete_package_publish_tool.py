# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	frappe.delete_doc("DocType", "Package Publish Tool", ignore_missing=True)
	frappe.delete_doc("DocType", "Package Document Type", ignore_missing=True)
	frappe.delete_doc("DocType", "Package Publish Target", ignore_missing=True)
