import frappe


def execute() -> None:
	for dt in frappe.get_all("Workflow", fields=["name", "document_type", "workflow_state_field"]):
		fieldname = frappe.db.get_value(
			"Custom Field", filters={"dt": dt.document_type, "fieldname": dt.workflow_state_field}
		)

		if fieldname:
			custom_field = frappe.get_doc("Custom Field", fieldname)
			custom_field.no_copy = 1
			custom_field.save()
