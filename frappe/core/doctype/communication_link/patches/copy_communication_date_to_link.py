import frappe


# copy communication_date from Communication to Communication Link
def execute():
	batch_size = 10_000

	while True:
		frappe.db.multisql(
			{
				"mariadb": """
					update `tabCommunication Link` cl
					inner join `tabCommunication` c on cl.parent = c.name
					set cl.communication_date = c.communication_date
					where cl.communication_date is null
					and c.communication_date is not null
					limit %s
				""",
				"postgres": """
					UPDATE "tabCommunication Link"
					SET communication_date = sub.communication_date
					FROM (
						SELECT cl.name, c.communication_date
						FROM "tabCommunication Link" cl
						JOIN "tabCommunication" c ON cl.parent = c.name
						WHERE cl.communication_date IS NULL
						AND c.communication_date IS NOT NULL
						LIMIT %s
					) AS sub
					WHERE "tabCommunication Link".name = sub.name
				""",
			},
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
