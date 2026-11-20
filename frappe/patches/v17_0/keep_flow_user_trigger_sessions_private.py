import frappe


def execute():
	"""What a Flow User's own trigger already started becomes theirs alone."""
	run, session = frappe.qb.DocType("Flow Run"), frappe.qb.DocType("Flow Session")
	for trigger in frappe.get_all("Flow Trigger", fields=["name", "owner"]):
		if "System Manager" in frappe.get_roles(trigger.owner):
			continue
		started = (
			frappe.qb.from_(run)
			.select(run.session)
			.where((run.trigger == trigger.name) & (run.owner == trigger.owner))
		)
		frappe.qb.update(session).set(session.personal_trigger, 1).where(session.name.isin(started)).run()
