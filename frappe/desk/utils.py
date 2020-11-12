# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

@frappe.whitelist(allow_guest=True)
def get_doctype_name(name):
	# translates the doctype name from url to name `sales-order` to `Sales Order`
	def get_name_map():
		name_map = {}
		for d in frappe.get_all('DocType'):
			name_map[d.name.lower().replace(' ', '-')] = d.name

		return name_map

	return frappe.cache().get_value('doctype_name_map', get_name_map).get(name, name)