import frappe


def execute():
	old_settings = {
		"Error Log": get_current_setting("clear_error_log_after"),
		"Activity Log": get_current_setting("clear_activity_log_after"),
		"Email Queue": get_current_setting("clear_email_queue_after"),
	}

	frappe.reload_doc("core", "doctype", "Logs To Clear")
	frappe.reload_doc("core", "doctype", "Log Settings")

	log_settings = frappe.get_doc("Log Settings")
	log_settings.add_default_logtypes()

	for doctype, retention in old_settings.items():
		if retention:
			log_settings.register_doctype(doctype, retention)

	log_settings.save()


def get_current_setting(fieldname):
	try:
		return frappe.db.get_single_value("Log Settings", fieldname)
	except Exception:
		# Field might be gone if patch is reattempted
		pass
