import frappe


def update_system_settings(args, commit=False):
	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
	if commit:
		frappe.db.commit()


def get_system_setting(key):
	return frappe.db.get_single_value("System Settings", key)


global_test_dependencies = ["User"]
