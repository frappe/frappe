"""
This api historically supports an email (only) inbox.
It is (mainly) implemented by a special type of view, the Inbox View.
The source is here: public/js/frappe/views/inbox/inbox_view.js

Currently, this Inbox View frames altered list and form views that make the main use of this inbox api.

TODO: View and api may transition to support a unified inbox in the future.
"""

import json

import frappe
from frappe.client import set_value


@frappe.whitelist()
def create_email_flag_queue(names, action):
	"""create email flag queue to mark email either as read or unread"""

	def mark_as_seen_unseen(name, action):
		doc = frappe.get_doc("Communication", name)
		if action == "Read":
			doc.add_seen()
		else:
			_seen = json.loads(doc._seen or "[]")
			_seen = [user for user in _seen if frappe.session.user != user]
			doc.db_set("_seen", json.dumps(_seen), update_modified=False)

	if not all([names, action]):
		return

	for name in json.loads(names or []):
		uid, seen_status, email_account = frappe.db.get_value(
			"Communication", name, ["ifnull(uid, -1)", "ifnull(seen, 0)", "email_account"]
		)

		# can not mark email SEEN or UNSEEN without uid
		if not uid or uid == -1:
			continue

		seen = 1 if action == "Read" else 0
		# check if states are correct
		if (action == "Read" and seen_status == 0) or (action == "Unread" and seen_status == 1):
			create_new = True
			email_flag_queue = frappe.db.sql(
				"""select name, action from `tabEmail Flag Queue`
				where communication = %(name)s and is_completed=0""",
				{"name": name},
				as_dict=True,
			)

			for queue in email_flag_queue:
				if queue.action != action:
					frappe.delete_doc("Email Flag Queue", queue.name, ignore_permissions=True)
				elif queue.action == action:
					# Read or Unread request for email is already available
					create_new = False

			if create_new:
				flag_queue = frappe.get_doc(
					{
						"uid": uid,
						"action": action,
						"communication": name,
						"doctype": "Email Flag Queue",
						"email_account": email_account,
					}
				)
				flag_queue.save(ignore_permissions=True)
				frappe.db.set_value("Communication", name, "seen", seen, update_modified=False)
				mark_as_seen_unseen(name, action)


@frappe.whitelist()
def mark_as_closed_open(communication: str, status: str):
	"""Set status to open or close"""
	set_value("Communication", communication, "status", status)


@frappe.whitelist()
def move_email(communication: str, email_account: str):
	"""Move email to another email account."""
	set_value("Communication", communication, "email_account", email_account)


@frappe.whitelist()
def mark_as_trash(communication: str):
	"""Set email status to trash."""
	set_value("Communication", communication, "email_status", "Trash")


@frappe.whitelist()
def mark_as_spam(communication: str, sender: str):
	"""Set email status to spam."""
	email_rule = frappe.db.get_value("Email Rule", {"email_id": sender})
	if not email_rule:
		frappe.get_doc({"doctype": "Email Rule", "email_id": sender, "is_spam": 1}).insert(
			ignore_permissions=True
		)
	set_value("Communication", communication, "email_status", "Spam")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read
	from frappe.modules import load_doctype_module

	com_doctypes = []
	if len(txt) < 2:

		for name in frappe.get_hooks("communication_doctypes"):
			try:
				module = load_doctype_module(name, suffix="_dashboard")
				if hasattr(module, "get_data"):
					for i in module.get_data()["transactions"]:
						com_doctypes += i["items"]
			except ImportError:
				pass
	else:
		com_doctypes = [
			d[0] for d in frappe.db.get_values("DocType", {"issingle": 0, "istable": 0, "hide_toolbar": 0})
		]

	return [
		[dt] for dt in com_doctypes if txt.lower().replace("%", "") in dt.lower() and dt in can_read
	]


@frappe.whitelist()
def relink(name, reference_doctype=None, reference_name=None):
	frappe.db.sql(
		"""update
			`tabCommunication`
		set
			reference_doctype = %s,
			reference_name = %s,
			status = "Linked"
		where
			communication_type = "Communication" and
			name = %s""",
		(reference_doctype, reference_name, name),
	)


def link_communication_to_document(
	doc, reference_doctype, reference_name, ignore_communication_links
):
	if not ignore_communication_links:
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.status = "Linked"
		doc.save(ignore_permissions=True)


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
