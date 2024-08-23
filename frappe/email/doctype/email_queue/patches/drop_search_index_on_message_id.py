import frappe


def execute():
	"""Drop search index on message_id"""

	if frappe.db.get_column_type("Email Queue", "message_id") == "text":
		return

	if index := frappe.db.get_column_index("tabEmail Queue", "message_id", unique=False):
		frappe.db.sql(f"ALTER TABLE `tabEmail Queue` DROP INDEX `{index.Key_name}`")
