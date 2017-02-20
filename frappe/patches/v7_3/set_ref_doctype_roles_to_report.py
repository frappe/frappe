# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", 'doctype', "report")
	frappe.reload_doc("core", 'doctype', "has_role")
	for data in frappe.get_all('Report', fields=["name"]):
		doc = frappe.get_doc('Report', data.name)
		doc.set_doctype_roles()
		for row in doc.roles:
			row.db_update()