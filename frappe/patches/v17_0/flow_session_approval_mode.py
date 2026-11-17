import frappe


def execute():
	"""The auto_approve check became the approval_mode select."""
	if not frappe.db.has_column("Flow Session", "auto_approve"):
		return
	frappe.db.sql(
		"""update `tabFlow Session`
		set approval_mode = case when auto_approve = 1 then 'Auto-approve' else 'Ask' end"""
	)
