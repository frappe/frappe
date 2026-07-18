import json

import frappe
from frappe.core.api.document import set_value


def get_email_accounts(user=None):
	if not user:
		user = frappe.session.user

	email_accounts = []

	accounts = frappe.get_all(
		"User Email",
		filters={"parent": user},
		fields=["email_account", "email_id", "enable_outgoing"],
		distinct=True,
		order_by="idx",
	)

	if not accounts:
		return {"email_accounts": [], "all_accounts": ""}

	all_accounts = ",".join(account.get("email_account") for account in accounts)
	if len(accounts) > 1:
		email_accounts.append({"email_account": all_accounts, "email_id": "All Accounts"})
	email_accounts.extend(accounts)

	email_accounts.extend(
		[
			{"email_account": "Sent", "email_id": "Sent Mail"},
			{"email_account": "Spam", "email_id": "Spam"},
			{"email_account": "Trash", "email_id": "Trash"},
		]
	)

	return {"email_accounts": email_accounts, "all_accounts": all_accounts}


def link_communication_to_document(doc, reference_doctype, reference_name, ignore_communication_links):
	if not ignore_communication_links:
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.status = "Linked"
		doc.save(ignore_permissions=True)


# `create_email_flag_queue`, `mark_as_closed_open`, `move_email`, `mark_as_trash`, `mark_as_spam` moved to frappe.email.api.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_EMAIL_API = {
	"create_email_flag_queue": "create_email_flag_queue",
	"mark_as_closed_open": "mark_as_closed_open",
	"move_email": "move_email",
	"mark_as_trash": "mark_as_trash",
	"mark_as_spam": "mark_as_spam",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_EMAIL_API.get(name):
		from frappe.email import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
