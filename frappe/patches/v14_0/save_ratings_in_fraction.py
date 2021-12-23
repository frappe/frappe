import frappe
from frappe.query_builder import DocType


def execute():
	rating_fields = frappe.get_all(
		"DocField", fields=["parent", "fieldname"], filters={"fieldtype": "Rating"}
	)

	custom_rating_fields = frappe.get_all(
		"Custom Field", fields=["dt", "fieldname"], filters={"fieldtype": "Rating"}
	)

	for _field in rating_fields + custom_rating_fields:
		doctype_name = _field.get("parent") or _field.get("dt")
		doctype = DocType(doctype_name)
		field = _field.fieldname

		# update NULL values to 0 to avoid data truncated error (temp)
		# commit for upcoming DLL
		frappe.qb.update(doctype).set(
			doctype[field], 0
		).where(
			doctype[field].isnull()
		).run()
		frappe.db.commit()

		# alter column types for rating fieldtype
		frappe.db.change_column_type(doctype_name, column=field, type="decimal(3,2)")

		# update data: int => decimal
		frappe.qb.update(doctype).set(
			doctype[field], doctype[field] / 5
		).run()

		# revert 0 to NULL conversion
		frappe.qb.update(doctype).set(
			doctype[field], None
		).where(
			doctype[field] == 0
		).run()

		# commit to flush updated rows
		frappe.db.commit()
