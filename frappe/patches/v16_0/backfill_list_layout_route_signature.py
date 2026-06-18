import frappe
from frappe.desk.doctype.list_layout.list_layout import compute_route_signature


def execute():
	"""Backfill route_signature for layouts migrated from List Filter."""
	if not frappe.db.table_exists("List Layout"):
		return

	if not frappe.db.has_column("List Layout", "route_signature"):
		return

	if not frappe.db.count("List Layout"):
		return

	while True:
		rows = frappe.get_all(
			"List Layout",
			fields=["name", "reference_doctype", "filters"],
			filters={"route_signature": ["is", "not set"]},
			limit=500,
		)
		if not rows:
			break

		for row in rows:
			signature = compute_route_signature(row.reference_doctype, row.filters)
			frappe.db.set_value(
				"List Layout",
				row.name,
				"route_signature",
				signature,
				update_modified=False,
			)
