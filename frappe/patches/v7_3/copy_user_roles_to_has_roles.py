# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", 'doctype', "user")
	frappe.reload_doc("core", 'doctype', "has_role")
	for data in frappe.get_all('User', fields = ["name"]):
		doc = frappe.get_doc('User', data.name)
		roles = [{'role': d.role} for d in doc.user_roles]
		doc.set('roles', roles)
		for role in doc.roles:
			role.db_update()