# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public email API — compose communications, manage the inbox and email queue.

Endpoints were consolidated from `frappe.core.doctype.communication.email`,
`frappe.email.inbox`, `frappe.email` and the Email Queue doctype; the old
dotted paths keep working via aliases in the original modules.
"""

import json
from datetime import datetime
from typing import Any

import frappe
import frappe.utils
from frappe import _
from frappe.core.api.document import set_value
from frappe.core.doctype.communication.email import _make, _mark_email_as_seen
from frappe.database.utils import commit_after_response
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.public_api import public
from frappe.utils import cint, now, now_datetime, sbool, time_diff_in_seconds


@public(group="Email")
@frappe.whitelist()
def make_communication(
	doctype: str | None = None,
	name: str | int | None = None,
	content: str | None = None,
	subject: str | None = None,
	sent_or_received: str = "Sent",
	sender: str | None = None,
	sender_full_name: str | None = None,
	recipients: str | list[str] | None = None,
	communication_medium: str = "Email",
	send_email: str | bool | int = False,
	print_html: str | None = None,
	print_format: str | None = None,
	attachments: str | list[str | dict[str, Any]] | None = None,
	send_me_a_copy: str | int | bool = False,
	cc: str | list[str] | None = None,
	bcc: str | list[str] | None = None,
	read_receipt: str | int | bool | None = None,
	print_letterhead: int | bool = True,
	letterhead: str | None = None,
	email_template: str | None = None,
	communication_type: str | None = None,
	send_after: str | datetime | None = None,
	print_language: str | None = None,
	now: int | bool = False,
	raw_html: int | bool = False,
	add_css: int | bool = True,
	in_reply_to: str | None = None,
	**kwargs: Any,
) -> dict[str, str]:
	"""Make a new communication. Checks for email permissions for specified Document.

	:param doctype: Reference DocType.
	:param name: Reference Document name.
	:param content: Communication body.
	:param subject: Communication subject.
	:param sent_or_received: Sent or Received (default **Sent**).
	:param sender: Communcation sender (default current user).
	:param recipients: Communication recipients as list.
	:param communication_medium: Medium of communication (default **Email**).
	:param send_email: Send via email (default **False**).
	:param print_html: HTML Print format to be sent as attachment.
	:param print_format: Print Format name of parent document to be sent as attachment.
	:param attachments: List of File names or dicts with keys "fname" and "fcontent"
	:param send_me_a_copy: Send a copy to the sender (default **False**).
	:param email_template: Template which is used to compose mail .
	:param send_after: Send after the given datetime.
	:param raw_html: Whether to use html version of email template
	:param add_css: Add default CSS from hooks/email_css to the email template (default **True**)
	:param in_reply_to: Name of the Communication document to which this communication is a reply.
	"""
	from frappe.utils.commands import warn

	if kwargs:
		warn(
			f"Options {kwargs} used in frappe.core.doctype.communication.email.make "
			"are deprecated or unsupported",
			category=DeprecationWarning,
		)

	if doctype and name:
		frappe.has_permission(doctype, doc=name, ptype="email", throw=True)

	if letterhead:
		frappe.has_permission("Letter Head", doc=letterhead, ptype="read", throw=True)

	if raw_html and not (
		email_template and frappe.get_cached_value("Email Template", email_template, "use_html")
	):
		warn(
			_(
				"Raw HTML can be used only with Email Templates having 'Use HTML' checked. "
				"Proceeding with plain text email."
			),
			category=UserWarning,
		)
		raw_html = False

	return _make(
		doctype=doctype,
		name=name,
		content=content,
		subject=subject,
		sent_or_received=sent_or_received,
		sender=sender,
		sender_full_name=sender_full_name,
		recipients=recipients,
		communication_medium=communication_medium,
		send_email=send_email,
		print_html=print_html,
		print_format=print_format,
		attachments=attachments,
		send_me_a_copy=cint(send_me_a_copy),
		cc=cc,
		bcc=bcc,
		read_receipt=cint(read_receipt),
		print_letterhead=print_letterhead,
		letterhead=letterhead,
		email_template=email_template,
		communication_type=communication_type,
		add_signature=False,
		send_after=send_after,
		print_language=print_language,
		now=now,
		raw_html=raw_html,
		add_css=add_css,
		in_reply_to=in_reply_to,
	)


@public(group="Email")
@frappe.whitelist(allow_guest=True, methods=("GET",))
def mark_email_as_seen(name: str | None = None) -> None:
	"""Serve the read-receipt tracking pixel and mark the email as read.

	:param name: name of the Communication the pixel was embedded in
	"""
	commit_after_response(lambda: _mark_email_as_seen(name))
	frappe.response.update(frappe.utils.get_imaginary_pixel_response())


@public(group="Email")
@frappe.whitelist()
def undo_email_send(communication_name: str) -> dict:
	"""Undo a just-sent email while it is still in the undo window.

	Deletes the queued email and the Communication, and returns the data
	needed to reopen the composer.

	:param communication_name: name of the Communication to be undone
	:return: The communication's data (subject, content, recipients, attachments, ...).
	"""
	communication = frappe.get_doc("Communication", communication_name)

	if communication.owner != frappe.session.user:
		frappe.throw(_("You are not authorized to undo this email"))

	if communication.sent_or_received != "Sent" or communication.communication_medium != "Email":
		frappe.throw(_("Failed to delete communication"))

	time_elapsed_in_seconds = time_diff_in_seconds(now_datetime(), communication.creation)
	if time_elapsed_in_seconds > 10:
		frappe.msgprint(
			_("Email undo window is over. Cannot undo email."), alert=True, indicator="red", raise_exception=1
		)

	email_queue_records = frappe.get_all(
		"Email Queue", filters={"communication": communication_name}, fields=["name", "status"]
	)

	for queue in email_queue_records:
		if queue.status != "Not Sent":
			frappe.msgprint(
				_("It is too late to undo this email. It is already being sent."),
				alert=True,
				indicator="red",
				raise_exception=1,
			)

	for queue in email_queue_records:
		frappe.delete_doc("Email Queue", queue.name, ignore_permissions=True)

	communication_data = {
		"subject": communication.subject,
		"content": communication.content,
		"recipients": communication.recipients,
		"cc": communication.cc,
		"bcc": communication.bcc,
		"doc": {"doctype": communication.reference_doctype, "name": communication.reference_name},
		"sender": communication.sender,
		"send_read_receipt": communication.read_receipt,
	}

	linked_files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Communication", "attached_to_name": communication_name},
		pluck="name",
	)

	if linked_files:
		for file_name in linked_files:
			frappe.db.set_value("File", file_name, {"attached_to_doctype": None, "attached_to_name": None})

	communication_data["attachments"] = linked_files

	communication.delete(ignore_permissions=True)

	return communication_data


@public(group="Email")
@frappe.whitelist()
def create_email_flag_queue(names: str | list, action: str) -> None:
	"""Queue marking of inbox emails as read or unread on the email server.

	:param names: names of the Communications to be marked
	:param action: "Read" or "Unread"
	"""

	def mark_as_seen_unseen(name, action):
		doc = frappe.get_lazy_doc("Communication", name)
		if action == "Read":
			doc.add_seen()
		else:
			_seen = json.loads(doc._seen or "[]")
			_seen = [user for user in _seen if frappe.session.user != user]
			doc.db_set("_seen", json.dumps(_seen), update_modified=False)

	if not all([names, action]):
		return

	for name in frappe.parse_json(names):
		uid, seen_status, email_account = frappe.db.get_value(
			"Communication", name, ["uid", "seen", "email_account"]
		)
		if not uid:
			uid = -1
		if not seen_status:
			seen_status = 0

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
					frappe.delete_doc("Email Flag Queue", queue.name, ignore_permissions=True, force=True)
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


@public(group="Email")
@frappe.whitelist()
def mark_as_closed_open(communication: str, status: str) -> None:
	"""Set an inbox email's status to Open or Closed.

	:param communication: name of the Communication
	:param status: "Open" or "Closed"
	"""
	set_value("Communication", communication, "status", status)


@public(group="Email")
@frappe.whitelist()
def move_email(communication: str, email_account: str) -> None:
	"""Move an inbox email to another email account.

	:param communication: name of the Communication
	:param email_account: name of the destination Email Account
	"""
	set_value("Communication", communication, "email_account", email_account)


@public(group="Email")
@frappe.whitelist()
def mark_as_trash(communication: str) -> None:
	"""Move an inbox email to trash.

	:param communication: name of the Communication
	"""
	set_value("Communication", communication, "email_status", "Trash")


@public(group="Email")
@frappe.whitelist()
def mark_as_spam(communication: str, sender: str) -> None:
	"""Mark an inbox email as spam and add a spam rule for its sender.

	:param communication: name of the Communication
	:param sender: email address the spam rule is created for
	"""
	email_rule = frappe.db.get_value("Email Rule", {"email_id": sender})
	if not email_rule:
		frappe.get_doc({"doctype": "Email Rule", "email_id": sender, "is_spam": 1}).insert(
			ignore_permissions=True
		)
	set_value("Communication", communication, "email_status", "Spam")


@public(group="Email")
@frappe.whitelist()
def get_contact_list(txt: str, page_length: int = 20, extra_filters: str | None = None) -> list[dict]:
	"""Return email ids for a multiselect field."""
	if extra_filters:
		extra_filters = frappe.parse_json(extra_filters)

	filters = [
		["Contact Email", "email_id", "is", "set"],
	]
	if extra_filters:
		filters.extend(extra_filters)

	fields = ["first_name", "middle_name", "last_name", "company_name"]
	contacts = frappe.get_list(
		"Contact",
		fields=["full_name", "`tabContact Email`.email_id"],
		filters=filters,
		or_filters=[[field, "like", f"%{txt}%"] for field in fields]
		+ [["Contact Email", "email_id", "like", f"%{txt}%"]],
		limit_page_length=page_length,
	)

	# The multiselect field will store the `label` as the selected value.
	# The `value` is just used as a unique key to distinguish between the options.
	# https://github.com/frappe/frappe/blob/6c6a89bcdd9454060a1333e23b855d0505c9ebc2/frappe/public/js/frappe/form/controls/autocomplete.js#L29-L35
	return [
		frappe._dict(
			value=d.email_id,
			label=d.email_id,
			description=d.full_name,
		)
		for d in contacts
	]


@public(group="Email")
@frappe.whitelist()
def relink_communication(
	name: str, reference_doctype: str | None = None, reference_name: str | None = None
) -> None:
	"""Link a communication to another reference document.

	:param name: name of the Communication
	:param reference_doctype: DocType of the new reference document
	:param reference_name: name of the new reference document
	"""
	frappe.has_permission("Communication", "write", name, throw=True)
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


@public(group="Email")
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_communication_doctype(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: str | list | dict
) -> list:
	"""Search doctypes a communication can be linked to.

	:param doctype: search doctype (unused, standard link search signature)
	:param txt: search text
	:param searchfield: standard link search signature field
	:param start: standard link search signature field
	:param page_len: standard link search signature field
	:param filters: standard link search signature field
	:return: Matching doctype names the user can read.
	"""
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read
	from frappe import _
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

	results = []
	txt_lower = txt.lower().replace("%", "")

	for dt in list(set(com_doctypes)):
		if dt in can_read:
			if txt_lower in dt.lower() or txt_lower in _(dt).lower():
				results.append([dt])

	return results


@public(group="Email")
@frappe.whitelist()
def retry_sending(queues: str | list[str]) -> None:
	"""Retry sending queued emails that errored out.

	:param queues: names of the Email Queue records to be retried
	"""
	if not frappe.has_permission("Email Queue", throw=True):
		return

	queues = frappe.parse_json(queues)

	if not queues:
		return

	# NOTE: this will probably work fine with the way current listview works (showing and selecting 20-20 records)
	# but, ideally this should be enqueued
	email_queue = frappe.qb.DocType("Email Queue")
	frappe.qb.update(email_queue).set(email_queue.status, "Not Sent").set(email_queue.modified, now()).set(
		email_queue.modified_by, frappe.session.user
	).where(email_queue.name.isin(queues) & email_queue.status == "Error").run()


@public(group="Email")
@frappe.whitelist()
def send_now(name: str | int, force_send: bool = False) -> None:
	"""Send a queued email immediately.

	:param name: name of the Email Queue record
	:param force_send: send even if sending is suspended or already attempted
	"""
	record = EmailQueue.find(name)
	if record:
		record.check_permission()
		record.send(force_send=force_send)


@public(group="Email")
@frappe.whitelist()
def toggle_sending(enable: bool | int | str) -> None:
	"""Suspend or resume sending of the email queue.

	:param enable: truthy to resume sending, falsy to suspend it
	"""
	frappe.only_for("System Manager")
	suspend_value = 0 if sbool(enable) else 1
	frappe.db.set_default("suspend_email_queue", suspend_value)

	action = "Resumed" if suspend_value == 0 else "Suspended"
	frappe.get_doc(
		{
			"doctype": "Activity Log",
			"user": frappe.session.user,
			"status": "Success",
			"subject": f"Email Queue sending {action.lower()}",
		}
	).insert(ignore_permissions=True, ignore_links=True)
