from werkzeug import Response

import frappe


def get_security_txt():
	response = Response()
	response.mimetype = "text/plain"
	[[policy, contact, preferred_language]] = frappe.db.get_values(
		"Security Settings", fieldname=["public_policy", "public_contact", "public_language"]
	)
	policy = policy or "https://frappe.io/security"
	contact = contact or "https://security.frappe.io"
	preferred_language = preferred_language or "en"
	response.data = (
		"# Read our security policy before reporting an issue\n"
		f"Policy: {policy}\n\n"
		"# Our security address\n"
		f"Contact: {contact}\n\n"
		"# We prefer talking in\n"
		f"Preferred-Languages: {preferred_language}"
	)
	return response
