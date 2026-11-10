import frappe


def execute():
	"""Drop the `anchors` column of Settings Block: a pane's order is the desk app's arrangement, then run order."""
	if frappe.db.has_column("Settings Block", "anchors"):
		frappe.db.drop_columns("Settings Block", ["anchors"])
