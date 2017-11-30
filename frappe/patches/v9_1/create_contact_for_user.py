# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	""" Create Contact for each User if not present """

	users = frappe.get_all('User', filters={"name": ('not in', 'Administrator, Guest')})
	for d in users:
		user = frappe.get_doc('User', d)
		if not frappe.db.get_value("Contact", {"email_id": user.email}):
			frappe.get_doc({
				"doctype": "Contact",
				"first_name": user.first_name,
				"last_name": user.last_name,
				"email_id": user.email,
				"user": user.name,
				"gender": user.gender,
				"phone": user.phone,
				"mobile_no": user.mobile_no
			}).insert(ignore_permissions=True)