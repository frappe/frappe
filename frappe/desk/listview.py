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

	subquery_condition = ''
	if current_filters:
		# get the subquery
		subquery = frappe.get_all(doctype,
			filters=current_filters, return_query = True)
		subquery_condition = ' and `tabToDo`.reference_name in ({subquery})'.format(subquery = subquery)

	todo_list = frappe.db.sql("""select `tabToDo`.owner as name, count(*) as count
		from
			`tabToDo`, `tabUser`
		where
			`tabToDo`.status='Open' and
			`tabToDo`.owner = `tabUser`.name and
			`tabUser`.user_type = 'System User' 
			{subquery_condition}
		group by
			`tabToDo`.owner
		order by
			count desc
		limit 50""".format(subquery_condition = subquery_condition), as_dict=True)

	return todo_list