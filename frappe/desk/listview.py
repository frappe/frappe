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
def get_user_assignments_and_count(doctype, current_filters):
	filtered_list = frappe.get_all(doctype,
		filters=current_filters)
	names = "'"+"','".join(list(map(lambda x: x.name, filtered_list)))+"'"

	if names:
		todo_list = sorted(frappe.db.sql("""select tabToDo.owner as name, count(*) as count from tabToDo, tabUser
										where
										tabToDo.status='open' and
										tabToDo.owner = tabUser.name and
										tabUser.user_type = 'System User' and
										tabToDo.reference_name in ({names})
										group by tabToDo.owner
										""".format(doctype = doctype, names = names), as_dict=True), key=lambda k: k['count'], reverse = True)
		return todo_list
	else:
		return []