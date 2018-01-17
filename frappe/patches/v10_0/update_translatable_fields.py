#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

def execute():
	frappe.db.sql('''
		UPDATE `tabDocField` 
		SET translatable = IF (fieldtype IN ("Data", "Select", "Text", "Small Text", "Text Editor"), 1, 0)
		''')

	frappe.db.sql('''
		UPDATE `tabCustom Field`
		SET translatable = IF (fieldtype IN ("Data", "Select", "Text", "Small Text", "Text Editor"), 1, 0)
	''')