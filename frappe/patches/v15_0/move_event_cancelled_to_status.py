import frappe


def execute():
	Event = frappe.qb.DocType("Event")
	query = (
		frappe.qb.update(Event)
		.set(Event.event_type, "Private")
		.set(Event.status, "Cancelled")
		.where(Event.event_type == "Cancelled")
	)
	query.run()
