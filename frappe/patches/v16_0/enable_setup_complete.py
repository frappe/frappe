import frappe


def execute():
	frappe.reload_doc("core", "doctype", "installed_application")
	frappe.reload_doc("core", "doctype", "installed_applications")

	is_setup_complete = frappe.db.get_single_value("System Settings", "setup_complete")
	for app_name in frappe.get_all("Installed Application", pluck="app_name"):
		has_setup_wizard = 0
		if app_name == "frappe":
			has_setup_wizard = 1
		elif frappe.get_hooks(app_name=app_name).get("setup_wizard_stages"):
			has_setup_wizard = 1

		if has_setup_wizard:
			frappe.db.set_value(
				"Installed Application",
				{"app_name": app_name},
				{
					"has_setup_wizard": 1,
					"is_setup_complete": is_setup_complete,
				},
			)
