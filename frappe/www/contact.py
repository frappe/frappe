# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

sitemap = 1


def get_context(context):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")

	if doc.query_options:
		query_options = [opt.strip() for opt in doc.query_options.replace(",", "\n").split("\n") if opt]
	else:
		query_options = ["Sales", "Support", "General"]

	out = {"query_options": query_options, "parents": [{"name": _("Home"), "route": "/"}]}
	out.update(doc.as_dict())

	return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=1000, seconds=60 * 60, methods=["POST"])
def send_message(sender, message, subject="Website Query"):
	if forward_to_email := frappe.db.get_single_value("Contact Us Settings", "forward_to_email"):
		frappe.sendmail(recipients=forward_to_email, reply_to=sender, content=message, subject=subject)

	frappe.sendmail(
		recipients=sender,
		content="Thank you for reaching out to us. We will get back to you at the earliest.",
		subject="We've received your query!",
	)

	# add to to-do ?
	frappe.get_doc(
		dict(
			doctype="Communication",
			sender=sender,
			subject=_("New Message from Website Contact Page"),
			sent_or_received="Received",
			content=message,
			status="Open",
		)
	).insert(ignore_permissions=True)
