import frappe


def execute():
	"""Mark unique fields used by field-based autoname as auto-generated."""

	rows = frappe.db.sql(
		"""
		SELECT
			dt.name AS doctype,
			SUBSTRING(dt.autoname, 7) AS fieldname
		FROM `tabDocType` dt
		WHERE dt.autoname LIKE 'field:%'
		""",
		as_dict=True,
	)

	for row in rows:
		frappe.db.set_value(
			"DocField",
			{"parent": row.doctype, "fieldname": row.fieldname, "unique": 1},
			"unique_auto_generated",
			1,
			update_modified=False,
		)
