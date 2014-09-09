# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	user_owner = frappe.db.get_value("Custom Field", {"fieldname": "user_owner"})
	if user_owner:
		frappe.delete_doc("Custom Field", user_owner)
