import frappe


def execute():
	names = frappe.get_all(
		"Flow Agent Memory",
		filters={"scope": "Agent", "source": ["in", ("Agent", "Feedback")], "status": "Active"},
		pluck="name",
	)
	if not names:
		return

	from frappe.flow.memory import store

	frappe.db.set_value("Flow Agent Memory", {"name": ["in", names]}, "status", "Pending")
	for name in names:
		store.remove(name)
