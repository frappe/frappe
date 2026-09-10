import itertools

import frappe
from frappe.database.schema import add_column
from frappe.query_builder.functions import Count

BATCH_SIZE = 2000


def execute():
	"""Add `_comment_count` where missing and fill it from `tabComment`.

	Custom doctypes are not re-synced by migrate, so the column has to be added here too.
	Holds one row per commented document in memory; stream per doctype if that ever matters.
	"""
	for doctype in frappe.get_all("DocType", {"istable": 0, "issingle": 0, "is_virtual": 0}, pluck="name"):
		if frappe.db.table_exists(doctype) and not frappe.db.has_column(doctype, "_comment_count"):
			add_column(doctype, "_comment_count", "Int", not_null=True, default="0")

	comment = frappe.qb.DocType("Comment")
	communication = frappe.qb.DocType("Communication")
	rows = (
		frappe.qb.from_(comment)
		.select(comment.reference_doctype, comment.reference_name, Count("*").as_("n"))
		.where(comment.comment_type == "Comment")
		.groupby(comment.reference_doctype, comment.reference_name)
	).run(as_dict=True) + (
		frappe.qb.from_(communication)
		.select(communication.reference_doctype, communication.reference_name, Count("*").as_("n"))
		.groupby(communication.reference_doctype, communication.reference_name)
	).run(as_dict=True)

	counts = {}
	for row in rows:
		if row.reference_doctype and row.reference_name:
			doc = counts.setdefault(row.reference_doctype, {}).setdefault(
				row.reference_name, {"_comment_count": 0}
			)
			doc["_comment_count"] += row.n

	for doctype, updates in counts.items():
		if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, "_comment_count"):
			continue

		pending = iter(updates.items())
		while batch := dict(itertools.islice(pending, BATCH_SIZE)):
			frappe.db.bulk_update(doctype, batch, chunk_size=BATCH_SIZE, update_modified=False)
			frappe.db.commit()
