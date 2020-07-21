import frappe

def execute():
	if frappe.db.db_type == "postgres":
		frappe.db.sql("""ALTER TABLE "__Auth" ALTER COLUMN "password" TYPE TEXT""")
	else:
		frappe.db.sql("""ALTER  TABLE `__Auth` MODIFY `password` TEXT NOT NULL""")
