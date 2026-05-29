import frappe
from frappe.doctypes import EmailAccount


def execute() -> None:
	accounts = frappe.db.get_all("Email Account", {"enable_incoming": 1, "enable_outgoing": 1}, pluck="name")
	for account in accounts:
		doc = EmailAccount.docs.get(account)

		if doc.reply_to_addresses:
			continue

		doc.append("reply_to_addresses", {"email": doc.email_id})
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_validate = True  # Ignore SMTP/IMAP validation
		doc.save()
