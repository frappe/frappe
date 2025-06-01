# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
from nts import _
from nts.utils import getdate


def execute(filters=None):
	priority_map = {"High": 3, "Medium": 2, "Low": 1}

	todo_list = nts.get_list(
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
			todo.date and getdate(todo.date) or getdate("1900-01-01"),
		),
		reverse=True,
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
		if todo.owner == nts.session.user or todo.assigned_by == nts.session.user:
			if todo.reference_type:
				todo.reference = """<a href="/app/Form/{}/{}">{}: {}</a>""".format(
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
					todo.owner,
					todo.assigned_by,
					todo.reference,
				]
			)

	return columns, result
