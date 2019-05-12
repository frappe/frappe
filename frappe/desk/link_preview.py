import frappe
from frappe.model import no_value_fields
import json

@frappe.whitelist()
def get_preview_data(doctype, docname, fields):
	fields = json.loads(fields)
	preview_fields = [field['name'] for field in fields if field['type'] not in no_value_fields]
	preview_fields.append(frappe.get_meta(doctype).get_title_field())
	if 'name' not in fields:
		preview_fields.append('name')
	preview_fields.append(frappe.get_meta(doctype).image_field)

	preview_data = frappe.get_list(doctype, filters={
		'name': docname
	}, fields=preview_fields, limit=1)
	if preview_data:
		preview_data = preview_data[0]

		preview_data = {k: v for k, v in preview_data.items() if v is not None}
		for k,v in preview_data.items():
			if frappe.get_meta(doctype).has_field(k):
				preview_data[k] = frappe.format(v,frappe.get_meta(doctype).get_field(k).fieldtype)

	if not preview_data:
		return None
	return preview_data

