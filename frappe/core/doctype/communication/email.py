# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import frappe
import frappe.email.smtp
from frappe import _
from frappe.database.utils import commit_after_response
from frappe.email.email_body import get_message_id
from frappe.utils import (
	cint,
	get_datetime,
	get_formatted_email,
	get_imaginary_pixel_response,
	get_string_between,
	list_to_str,
	now_datetime,
	parse_addr,
	split_emails,
	time_diff_in_seconds,
	validate_email_address,
)

if TYPE_CHECKING:
	from frappe.core.doctype.communication.communication import Communication


def _make(
	doctype=None,
	name=None,
	content=None,
	subject=None,
	sent_or_received="Sent",
	sender=None,
	sender_full_name=None,
	recipients=None,
	communication_medium="Email",
	send_email=False,
	print_html=None,
	print_format=None,
	attachments=None,
	send_me_a_copy=False,
	cc=None,
	bcc=None,
	read_receipt=None,
	print_letterhead=True,
	letterhead=None,
	email_template=None,
	communication_type=None,
	add_signature=True,
	send_after=None,
	print_language=None,
	now=False,
	raw_html=False,
	add_css=True,
	in_reply_to=None,
) -> dict[str, str]:
	"""Internal method to make a new communication that ignores Permission checks."""

	sender = sender or get_formatted_email(frappe.session.user)
	recipients = list_to_str(recipients) if isinstance(recipients, list) else recipients
	cc = list_to_str(cc) if isinstance(cc, list) else cc
	bcc = list_to_str(bcc) if isinstance(bcc, list) else bcc

	comm: Communication = frappe.get_doc(
		{
			"doctype": "Communication",
			"subject": subject,
			"content": content,
			"sender": sender,
			"sender_full_name": sender_full_name,
			"recipients": recipients,
			"cc": cc or None,
			"bcc": bcc or None,
			"communication_medium": communication_medium,
			"sent_or_received": sent_or_received,
			"reference_doctype": doctype,
			"reference_name": name,
			"email_template": email_template,
			"message_id": get_string_between("<", get_message_id(), ">"),
			"read_receipt": read_receipt,
			"has_attachment": 1 if attachments else 0,
			"communication_type": communication_type,
			"send_after": send_after,
			"in_reply_to": in_reply_to,
		}
	)
	comm.flags.skip_add_signature = not add_signature or (
		raw_html and email_template and frappe.get_cached_value("Email Template", email_template, "use_html")
	)
	comm.insert(ignore_permissions=True)

	# if not committed, delayed task doesn't find the communication
	if attachments:
		if isinstance(attachments, str):
			attachments = json.loads(attachments)
		add_attachments(comm.name, attachments)

	if cint(send_email):
		if not comm.get_outgoing_email_account():
			frappe.throw(
				_(
					"Unable to send mail because of a missing email account. Please setup default Email Account from Settings > Email Account"
				),
				exc=frappe.OutgoingEmailError,
			)

		comm.send_email(
			print_html=print_html,
			print_format=print_format,
			send_me_a_copy=send_me_a_copy,
			print_letterhead=print_letterhead,
			letterhead=letterhead,
			print_language=print_language,
			now=now,
			raw_html=raw_html,
			add_css=add_css,
		)

	emails_not_sent_to = comm.exclude_emails_list(include_sender=send_me_a_copy)

	return {"name": comm.name, "emails_not_sent_to": ", ".join(emails_not_sent_to)}


def validate_email(doc: "Communication") -> None:
	"""Validate Email Addresses of Recipients and CC"""
	if (
		doc.communication_type != "Communication"
		or doc.communication_medium != "Email"
		or doc.flags.in_receive
	):
		return

	# validate recipients
	for email in split_emails(doc.recipients):
		validate_email_address(email, throw=True)

	# validate CC
	for email in split_emails(doc.cc):
		validate_email_address(email, throw=True)

	for email in split_emails(doc.bcc):
		validate_email_address(email, throw=True)


def set_incoming_outgoing_accounts(doc):
	from frappe.email.doctype.email_account.email_account import EmailAccount

	incoming_email_account = EmailAccount.find_incoming(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype
	)
	doc.incoming_email_account = incoming_email_account.email_id if incoming_email_account else None

	doc.outgoing_email_account = EmailAccount.find_outgoing(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype
	)

	if doc.sent_or_received == "Sent":
		doc.db_set("email_account", doc.outgoing_email_account.name)


def add_attachments(name: str, attachments: Iterable[str | dict]) -> None:
	"""Add attachments to the given Communication

	:param name: Communication name
	:param attachments: File names or dicts with keys "fname" and "fcontent"
	"""
	# loop through attachments
	for a in attachments:
		if isinstance(a, str):
			attach = frappe.db.get_value("File", {"name": a}, ["file_url", "is_private"], as_dict=1)
			file_args = {
				"file_url": attach.file_url,
				"is_private": attach.is_private,
			}
		elif isinstance(a, dict) and "fcontent" in a and "fname" in a:
			# dict returned by frappe.attach_print()
			file_args = {
				"file_name": a["fname"],
				"content": a["fcontent"],
				"is_private": 1,
			}
		else:
			continue

		file_args.update(
			{
				"attached_to_doctype": "Communication",
				"attached_to_name": name,
				"folder": "Home/Attachments",
			}
		)

		_file = frappe.new_doc("File")
		_file.update(file_args)
		_file.save(ignore_permissions=True)


def _mark_email_as_seen(name):
	try:
		update_communication_as_read(name)
	except Exception:
		frappe.log_error("Unable to mark as seen", None, "Communication", name)


def update_communication_as_read(name):
	if not name or not isinstance(name, str):
		return

	communication = frappe.db.get_value("Communication", name, "read_by_recipient", as_dict=True)

	if not communication or communication.read_by_recipient:
		return

	frappe.db.set_value(
		"Communication",
		name,
		{"read_by_recipient": 1, "delivery_status": "Read", "read_by_recipient_on": get_datetime()},
	)


# `make`, `mark_email_as_seen`, `undo_email_send` moved to frappe.email.api.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_EMAIL_API = {
	"make": "make_communication",
	"mark_email_as_seen": "mark_email_as_seen",
	"undo_email_send": "undo_email_send",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_EMAIL_API.get(name):
		from frappe.email import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
