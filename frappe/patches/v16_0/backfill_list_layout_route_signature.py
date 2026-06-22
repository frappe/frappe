import frappe
from frappe.desk.doctype.list_layout.list_layout import compute_route_signature

BATCH_SIZE = 500


def execute():
	"""Backfill route_signature for layouts migrated from List Filter."""
	if not frappe.db.table_exists("List Layout"):
		return

	if not frappe.db.has_column("List Layout", "route_signature"):
		return

	table = frappe.qb.DocType("List Layout")
	frappe.db.auto_commit_on_many_writes = 1
	try:
		while True:
			# Only NULL rows need backfill. `["is", "not set"]` also matches `""`, which is the
			# valid signature for empty filters and caused an infinite loop on those records.
			rows = (
				frappe.qb.from_(table)
				.select(table.name, table.reference_doctype, table.filters)
				.where(table.route_signature.isnull())
				.limit(BATCH_SIZE)
				.run(as_dict=True)
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
	finally:
		frappe.db.auto_commit_on_many_writes = 0
