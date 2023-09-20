import frappe


def execute():
	"""Drop search index on message_id"""

	if frappe.db.get_column_type("Email Queue", "message_id") == "text":
		return

	index = frappe.db.get_column_index("tabEmail Queue", "message_id", unique=False)
	if index:
		if frappe.db.db_type == "postgres":
			frappe.db.sql(f"DROP INDEX IF EXISTS {index.name};")
		elif frappe.db.db_type == "mariadb":
			frappe.db.sql(f"ALTER TABLE `tabEmail Queue` DROP INDEX `{index.Key_name}`")
