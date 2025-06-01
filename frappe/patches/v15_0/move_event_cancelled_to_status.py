import nts


def execute():
	Event = nts.qb.DocType("Event")
	query = (
		nts.qb.update(Event)
		.set(Event.event_type, "Private")
		.set(Event.status, "Cancelled")
		.where(Event.event_type == "Cancelled")
	)
	query.run()
