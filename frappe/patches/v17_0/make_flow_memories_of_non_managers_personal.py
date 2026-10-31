import frappe


def execute():
	"""Only those who manage an agent write what it remembers for everyone; what others wrote becomes theirs."""
	rows = frappe.get_all(
		"Flow Agent Memory", filters={"scope": "Agent"}, fields=["name", "agent", "modified_by"]
	)
	manages = {}
	moved = False
	for row in rows:
		key = (row.agent, row.modified_by)
		if key not in manages:
			manages[key] = row.modified_by == "Administrator" or frappe.has_permission(
				"Flow Agent", "write", row.agent, user=row.modified_by
			)
		if not manages[key]:
			frappe.db.set_value(
				"Flow Agent Memory",
				row.name,
				{"scope": "User", "user": row.modified_by},
				update_modified=False,
			)
			moved = True
	if moved:
		from frappe.flow.memory import store

		store.drop_table()
