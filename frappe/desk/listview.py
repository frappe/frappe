# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import json


@frappe.whitelist()
def get_list_settings(doctype):
	try:
		return frappe.get_cached_doc("List View Setting", doctype)
	except frappe.DoesNotExistError:
		frappe.clear_messages()


@frappe.whitelist()
def set_list_settings(doctype, values):
	try:
		doc = frappe.get_doc("List View Setting", doctype)
	except frappe.DoesNotExistError:
		doc = frappe.new_doc("List View Setting")
		doc.name = doctype
		frappe.clear_messages()
	doc.update(json.loads(values))
	doc.save()

@frappe.whitelist()
def get_user_assignments_and_count():
	user_list = frappe.get_list("User", filters={"user_type": "System User"})
	assignment_data = sorted([{"count":frappe.db.count('ToDo', filters = {'reference_type': 'Issue', 'owner': user['name'], 'status': 'Open'}),
						"name": user['name']} for user in user_list], key=lambda k: k['count'], reverse = True)
	return assignment_data