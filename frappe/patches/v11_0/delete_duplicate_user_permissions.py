import frappe


def execute() -> None:
	duplicateRecords = frappe.db.sql(
		"""select count(name) as `count`, allow, user, for_value
		from `tabUser Permission`
		group by allow, user, for_value
		having count(*) > 1 """,
		as_dict=1,
	)

	for record in duplicateRecords:
		frappe.db.sql(
			f"""delete from `tabUser Permission`
			where allow=%s and user=%s and for_value=%s limit {record.count - 1}""",
			(record.allow, record.user, record.for_value),
		)
