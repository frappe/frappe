# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def update(ml):
	"""update modules"""
	frappe.db.set_global('hidden_modules', ml)
	frappe.msgprint(frappe._('Updated'))
	frappe.clear_cache()
