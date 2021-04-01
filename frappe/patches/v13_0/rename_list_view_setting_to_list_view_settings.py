# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	if frappe.db.table_exists('List View Setting'):
		if not frappe.db.table_exists('List View Settings'):
			frappe.reload_doc("desk", "doctype", "List View Settings")

		existing_list_view_settings = frappe.get_all('List View Settings', as_list=True)
		for list_view_setting in frappe.get_all('List View Setting', fields = ['disable_count', 'disable_sidebar_stats', 'disable_auto_refresh', 'name']):
			name = list_view_setting.pop('name')
			if name not in [x[0] for x in existing_list_view_settings]:
				list_view_setting['doctype'] = 'List View Settings'
				list_view_settings = frappe.get_doc(list_view_setting)
				# setting name here is necessary because autoname is set as prompt
				list_view_settings.name = name
				list_view_settings.insert()

		frappe.delete_doc("DocType", "List View Setting", force=True)
		frappe.db.commit()
