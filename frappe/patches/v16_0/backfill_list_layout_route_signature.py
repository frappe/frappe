import frappe
from frappe.desk.doctype.list_filter.list_filter import compute_route_signature

BATCH_SIZE = 500


def execute():
	"""Backfill route_signature for saved list filters."""
	if not frappe.db.table_exists("List Filter"):
		return

	if not frappe.db.has_column("List Filter", "route_signature"):
		return

	table = frappe.qb.DocType("List Filter")
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
					"List Filter",
					row.name,
					"route_signature",
					signature,
					update_modified=False,
				)
	finally:
		frappe.db.auto_commit_on_many_writes = 0
