# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if not frappe.db.exists('DocType', 'Has Role'):
		frappe.rename_doc('DocType', 'Page Role', 'Has Role')