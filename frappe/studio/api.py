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


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	controller = get_controller(doctype)
	whitelisted_methods = []

	for method in controller.__dict__:
		if callable(getattr(controller, method)):
			try:
				is_whitelisted(getattr(controller, method))
				whitelisted_methods.append(method)
			except Exception:
				# not whitelisted
				continue

	return whitelisted_methods
