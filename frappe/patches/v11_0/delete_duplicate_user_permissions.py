import frappe

def execute():
	frappe.db.sql("""DELETE from `tabUser Permission` where name not in
		(Select * from
			(SELECT name FROM `tabUser Permission` GROUP BY allow, user, for_value)
		as retain)
	""") # https://stackoverflow.com/a/4685232