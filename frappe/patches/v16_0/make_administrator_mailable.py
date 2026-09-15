import frappe

PLACEHOLDER_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_EMAIL = "admin@frappe.local"


def execute():
	"""Let transactional auth mail reach Administrator.

	`admin@example.com` was globally unsubscribed by `install_fixtures.add_unsubscribe()`,
	so `QueueBuilder.process()` dropped every recipient before writing an Email Queue row:
	2FA enrolment and OTP secret reset mails vanished without a trace.
	"""
	frappe.db.delete("Email Unsubscribe", {"email": PLACEHOLDER_ADMIN_EMAIL})

	# Only touch sites that never set a real address.
	if frappe.db.get_value("User", "Administrator", "email") == PLACEHOLDER_ADMIN_EMAIL:
		frappe.db.set_value("User", "Administrator", "email", DEFAULT_ADMIN_EMAIL)
