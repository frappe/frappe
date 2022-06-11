import frappe


def execute():
	logging_doctypes = {
		"Error Log": get_current_setting("clear_error_log_after") or 30,
		"Activity Log": get_current_setting("clear_activity_log_after") or 90,
		"Email Queue": get_current_setting("clear_email_queue_after") or 30,
		"Route History": 90,
		"Error Snapshot": 30,
		"Scheduled Job Log": 90,
	}

	frappe.reload_doc("core", "doctype", "Logs To Clear")
	frappe.reload_doc("core", "doctype", "Log Settings")

	log_settings = frappe.get_doc("Log Settings")

	for doctype, days in logging_doctypes.items():
		log_settings.register_doctype(doctype, days)

	log_settings.save()


def get_current_setting(fieldname):
	try:
		return frappe.db.get_single_value("Log Settings", fieldname)
	except Exception:
		pass
