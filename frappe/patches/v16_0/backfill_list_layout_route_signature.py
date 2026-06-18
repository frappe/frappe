import frappe
from frappe.desk.doctype.list_layout.list_layout import compute_route_signature


def execute():
	"""Backfill route_signature for layouts migrated from List Filter."""
	if not frappe.db.table_exists("tabList Layout"):
		return

	if not frappe.db.has_column("List Layout", "route_signature"):
		return

	for row in frappe.get_all(
		"List Layout",
		fields=["name", "reference_doctype", "filters", "route_signature"],
		filters={"route_signature": ["in", ["", None]]},
	):
		signature = compute_route_signature(row.reference_doctype, row.filters)
		if signature:
			frappe.db.set_value(
				"List Layout",
				row.name,
				"route_signature",
				signature,
				update_modified=False,
			)
