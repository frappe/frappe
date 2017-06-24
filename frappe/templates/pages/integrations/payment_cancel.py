# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals
import frappe

def get_context(context):
	token = frappe.local.form_dict.token

	if token:
		frappe.db.set_value("Integration Request", token, "status", "Cancelled")
		frappe.db.commit()
