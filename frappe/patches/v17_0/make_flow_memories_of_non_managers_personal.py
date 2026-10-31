from collections import defaultdict

import frappe


def execute():
	"""Only those who manage an agent write what it remembers for everyone; what others wrote becomes theirs."""
	from frappe.flow.memory import store

	manages = {}
	moved = defaultdict(list)
	for row in frappe.get_all(
		"Flow Agent Memory", filters={"scope": "Agent"}, fields=["name", "agent", "modified_by"]
	):
		key = (row.agent, row.modified_by)
		if key not in manages:
			# a writer since deleted can't be asked, so their memories stay shared
			manages[key] = not frappe.db.exists("User", row.modified_by) or frappe.has_permission(
				"Flow Agent", "write", row.agent, user=row.modified_by
			)
		if not manages[key]:
			moved[row.modified_by].append(row.name)

	for user, names in moved.items():
		frappe.db.set_value(
			"Flow Agent Memory",
			{"name": ("in", names)},
			{"scope": "User", "user": user},
			update_modified=False,
		)
		store.make_personal(names, user)
