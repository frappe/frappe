# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if frappe.db.has_column('DocField', 'show_days'):
		frappe.db.sql('alter table tabDocField drop column show_days')

	if frappe.db.has_column('DocField', 'show_seconds'):
		frappe.db.sql('alter table tabDocField drop column show_seconds')

	frappe.clear_cache(doctype='DocField')