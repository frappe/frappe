import frappe


# copy communication_date from Communication to Communication Link
def execute():
	batch_size = 10_000

	while True:
		frappe.db.sql(
			"""
			update `tabCommunication Link` cl
			inner join `tabCommunication` c on cl.parent = c.name
			set cl.communication_date = c.communication_date
			where cl.communication_date is null
			and c.communication_date is not null
			limit %s
			""",
			(batch_size,),
		)

		frappe.db.commit()

		if not frappe.db.sql(
			"""
			select 1 from `tabCommunication Link` cl
			inner join `tabCommunication` c on cl.parent = c.name
			where cl.communication_date is null
			and c.communication_date is not null
			limit 1
			"""
		):
			break
