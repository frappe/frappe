# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if not frappe.db.exists('DocType', 'Has Role'):
		frappe.rename_doc('DocType', 'Page Role', 'Has Role')

	frappe.reload_doc("core", 'doctype', "page")
	frappe.reload_doc("core", 'doctype', "report")
	frappe.reload_doc("core", 'doctype', "user")
	frappe.reload_doc("core", 'doctype', "has_role")