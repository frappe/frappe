# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	priority_map = {"High": 3, "Medium": 2, "Low": 1}

	todo_list = frappe.get_list(
		"ToDo",
		fields=[
			"name",
			"date",
			"description",
			"priority",
			"reference_type",
			"reference_name",
			"assigned_by",
			"owner",
		],
		filters={"status": "Open"},
	)

	todo_list.sort(
		key=lambda todo: (
			priority_map.get(todo.priority, 0),
			(todo.date and getdate(todo.date)) or getdate("1900-01-01"),
		),
		reverse=True,
	)

	full_names = {}
	if users := {user for todo in todo_list for user in (todo.owner, todo.assigned_by) if user}:
		full_names = dict(
			frappe.get_all(
				"User", filters={"name": ("in", users)}, fields=["name", "full_name"], as_list=True
			)
		)

	columns = [
		_("ID") + ":Link/ToDo:90",
		_("Priority") + "::60",
		_("Date") + ":Date",
		_("Description") + "::150",
		_("Assigned To/Owner") + ":Data:120",
		_("Assigned By") + ":Data:120",
		_("Reference") + "::200",
	]

	result = []
	for todo in todo_list:
		if todo.owner == frappe.session.user or todo.assigned_by == frappe.session.user:
			if todo.reference_type:
				todo.reference = """<a href="/desk/Form/{}/{}">{}: {}</a>""".format(
					todo.reference_type,
					todo.reference_name,
					todo.reference_type,
					todo.reference_name,
				)
			else:
				todo.reference = None
			result.append(
				[
					todo.name,
					todo.priority,
					todo.date,
					todo.description,
					full_names.get(todo.owner) or todo.owner,
					full_names.get(todo.assigned_by) or todo.assigned_by,
					todo.reference,
				]
			)

	return columns, result
