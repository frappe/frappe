import frappe


def execute():
	"""Migrate Server Script's `disabled` field data to the new `enabled` field."""
	if not frappe.db.has_column("Server Script", "disabled"):
		return

	frappe.reload_doctype("Server Script")

	frappe.db.sql(
		"""
		UPDATE `tabServer Script`
		SET enabled = IF(disabled = 1, 0, 1)
		"""
	)
