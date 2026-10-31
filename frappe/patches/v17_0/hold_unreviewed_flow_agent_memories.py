import frappe


def execute():
	reviewers = {"Administrator", *frappe.get_all("Has Role", {"role": "System Manager"}, pluck="parent")}
	names = [
		row.name
		for row in frappe.get_all(
			"Flow Agent Memory",
			filters={"scope": "Agent", "status": "Active"},
			fields=["name", "source", "modified_by"],
		)
		# an agent may have rewritten a manual memory, which kept its source
		if row.source != "Manual" or row.modified_by not in reviewers
	]
	if not names:
		return

	from frappe.flow.memory import store

	frappe.db.set_value(
		"Flow Agent Memory", {"name": ["in", names]}, "status", "Pending", update_modified=False
	)
	store.drop_table()
