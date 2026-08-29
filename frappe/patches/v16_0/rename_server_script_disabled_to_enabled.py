import frappe


def execute():
	"""Migrate Server Script's `disabled` field data to the new `enabled` field."""
	if not frappe.db.has_column("Server Script", "disabled"):
		return

	frappe.reload_doctype("Server Script")

	frappe.db.sql(
		"""
		UPDATE `tabServer Script`
		SET enabled = CASE WHEN disabled = 1 THEN 0 ELSE 1 END
		"""
	)
