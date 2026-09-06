import frappe


def execute():
	"""Seed SMS Settings.allowed_roles with System Manager on existing sites."""
	frappe.reload_doctype("SMS Settings")

	sms_settings = frappe.get_single("SMS Settings")
	if sms_settings.get("allowed_roles"):
		return

	sms_settings.append("allowed_roles", {"role": "System Manager"})
	sms_settings.flags.ignore_mandatory = True
	sms_settings.save()
