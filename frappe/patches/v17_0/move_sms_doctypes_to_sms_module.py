import frappe


def execute():
	"""Create the SMS Module Def and re-point SMS DocTypes to it.

	On existing sites the SMS tables already exist, so schema_enabled=1.
	The module field in tabDocType is updated to match the moved JSON files.
	"""
	if not frappe.db.exists("Module Def", "SMS"):
		tables_exist = frappe.db.table_exists("SMS Log")
		frappe.get_doc(
			{
				"doctype": "Module Def",
				"module_name": "SMS",
				"app_name": "frappe",
				"schema_enabled": 1 if tables_exist else 0,
			}
		).insert(ignore_permissions=True)

	frappe.db.set_value(
		"DocType",
		{"name": ("in", ("SMS Log", "SMS Parameter", "SMS Settings"))},
		"module",
		"SMS",
	)
