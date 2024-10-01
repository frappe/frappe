import frappe
from frappe.model import display_fieldtypes, no_value_fields


@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	name_field = frappe._dict(
		{
			"fieldname": "name",
			"fieldtype": "Data",
			"label": "ID",
		}
	)
	fields.append(name_field)
	return [field for field in fields if field.fieldtype not in no_value_fields + display_fieldtypes]
