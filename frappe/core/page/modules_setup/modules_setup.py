# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def update(ml):
	"""update modules"""
	frappe.db.set_global('hidden_modules', ml)
	frappe.msgprint(frappe._('Updated'))
	frappe.clear_cache()

def get_context(context):
	context.icons = frappe.db.get_all('Desktop Icon',
			fields='*', filters={'standard': 1}, order_by='idx')
	context.users = frappe.db.get_all('User', filters={'user_type': 'System User', 'enabled': 1},
		fields = ['name', 'first_name', 'last_name'])
	print context.icons
