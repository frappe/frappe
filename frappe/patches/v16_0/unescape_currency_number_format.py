import frappe


def execute():
	"""Repair the Swiss number format that site install stored SQL-escaped."""
	frappe.db.set_value(
		"Currency",
		{"number_format": ("in", ("#''###.##", "#\\'###.##"))},
		"number_format",
		"#'###.##",
		update_modified=False,
	)
