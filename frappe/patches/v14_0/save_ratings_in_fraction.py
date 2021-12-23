import frappe

def execute():
	rating_fields = frappe.get_all("DocField", fields=["parent", "fieldname"], filters={"fieldtype": "Rating"})

	custom_rating_fields = frappe.get_all("Custom Field", fields=["dt", "fieldname"], filters={"fieldtype": "Rating"})

	for field in rating_fields + custom_rating_fields:
		doctype_name = field.get("parent") or field.get("dt")
		doctype = frappe.qb.DocType(doctype_name)
		field = field.fieldname
		(frappe.qb.update(doctype_name).set(doctype[field], doctype[field]/5)).run()
