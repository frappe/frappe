#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

def execute():
	'''
	Enable translatable in these fields
	- Customer Name
	- Supplier Name
	- Contact Name
	- Item Name/ Description
	- Address
	'''

	frappe.reload_doc('core', 'doctype', 'docfield')
	frappe.reload_doc('custom', 'doctype', 'custom_field')

	# frappe.db.sql('''
	# 	UPDATE `tabDocField`
	# 	SET translatable = IF (fieldtype IN ("Data", "Select", "Text", "Small Text", "Text Editor"), 0, 0)
	# ''')

	# frappe.db.set_value('DocField')
	# frappe.db.sql('''
	# 	UPDATE `tabCustom Field`
	# 	SET translatable = IF (fieldtype IN ("Data", "Select", "Text", "Small Text", "Text Editor"), 1, 0)
	# ''')