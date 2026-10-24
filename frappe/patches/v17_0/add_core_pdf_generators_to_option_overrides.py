import frappe


def execute():
	core = (
		frappe.db.get_value("DocField", {"parent": "Print Format", "fieldname": "pdf_generator"}, "options")
		or ""
	).split("\n")

	for setter in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Print Format", "field_name": "pdf_generator", "property": "options"},
		fields=["name", "value"],
	):
		extra = [o for o in (setter.value or "").split("\n") if o and o not in core and o != "wkhtmltopdf"]
		if extra:
			frappe.db.set_value("Property Setter", setter.name, "value", "\n".join(core + extra))
		else:
			frappe.delete_doc("Property Setter", setter.name, ignore_permissions=True)

	frappe.clear_cache(doctype="Print Format")
