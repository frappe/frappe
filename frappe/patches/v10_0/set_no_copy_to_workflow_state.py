import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

def execute():
	for dt in frappe.get_all("Workflow", fields=['name', 'document_type', 'workflow_state_field']):
		custom_field_name = "{0}-{1}".format(dt.document_type, dt.workflow_state_field)

		custom_field = frappe.get_doc("Custom Field", custom_field_name)
		custom_field.no_copy = 1
		custom_field.save()
