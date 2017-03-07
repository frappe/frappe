# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for doctype in ['UserRole', 'Event Role']:
		if frappe.db.exists('DocType', doctype):
			frappe.delete_doc('DocType', doctype)