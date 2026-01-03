import frappe


# copy communication_date from Communication to Communication Link
def execute():
	batch_size = 10_000

	while True:
		if frappe.db.db_type == "postgres":
			# Postgres doesn't support UPDATE..JOIN..LIMIT.
			# Use UPDATE..FROM and limit via ctid selection.
			frappe.db.sql(
				"""
				UPDATE "tabCommunication Link" cl
				SET communication_date = c.communication_date
				FROM "tabCommunication" c
				WHERE cl.parent = c.name
				  AND cl.communication_date IS NULL
				  AND c.communication_date IS NOT NULL
				  AND cl.ctid IN (
						SELECT cl2.ctid
						FROM "tabCommunication Link" cl2
						JOIN "tabCommunication" c2 ON cl2.parent = c2.name
						WHERE cl2.communication_date IS NULL
						  AND c2.communication_date IS NOT NULL
						LIMIT %s
				  )
				""",
				(batch_size,),
			)

			frappe.db.commit()

			if not frappe.db.sql(
				"""
				SELECT 1
				FROM "tabCommunication Link" cl
				JOIN "tabCommunication" c ON cl.parent = c.name
				WHERE cl.communication_date IS NULL
				  AND c.communication_date IS NOT NULL
				LIMIT 1
				"""
			):
				break

		else:
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
