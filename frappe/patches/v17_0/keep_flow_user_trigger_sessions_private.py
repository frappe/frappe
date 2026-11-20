import frappe


def execute():
	"""What a Flow User's own trigger already started becomes theirs alone."""
	for trigger in frappe.get_all("Flow Trigger", fields=["name", "owner"]):
		if "System Manager" in frappe.get_roles(trigger.owner):
			continue
		runs = {"trigger": trigger.name, "owner": trigger.owner}
		if sessions := frappe.get_all("Flow Run", runs, pluck="session"):
			frappe.db.set_value(
				"Flow Session", {"name": ("in", sessions)}, "personal_trigger", 1, update_modified=False
			)
