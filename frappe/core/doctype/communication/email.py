# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from typing import TYPE_CHECKING

import frappe
import frappe.email.smtp
from frappe import _
from frappe.email.email_body import get_message_id
from frappe.utils import (
	cint,
	get_datetime,
	get_formatted_email,
	get_string_between,
	list_to_str,
	split_emails,
	validate_email_address,
)

if TYPE_CHECKING:
	from frappe.core.doctype.communication.communication import Communication


@frappe.whitelist()
def make(
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
	attachments="[]",
	send_me_a_copy=False,
	cc=None,
	bcc=None,
	read_receipt=None,
	print_letterhead=True,
	email_template=None,
	communication_type=None,
	**kwargs,
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
	:param attachments: List of attachments as list of files or JSON string.
	:param send_me_a_copy: Send a copy to the sender (default **False**).
	:param email_template: Template which is used to compose mail .
	"""
	if kwargs:
		from frappe.utils.commands import warn

		warn(
			f"Options {kwargs} used in frappe.core.doctype.communication.email.make "
			"are deprecated or unsupported",
			category=DeprecationWarning,
		)

	if doctype and name and not frappe.has_permission(doctype=doctype, ptype="email", doc=name):
		raise frappe.PermissionError(f"You are not allowed to send emails related to: {doctype} {name}")

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
		email_template=email_template,
		communication_type=communication_type,
		add_signature=False,
	)


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
	attachments="[]",
	send_me_a_copy=False,
	cc=None,
	bcc=None,
	read_receipt=None,
	print_letterhead=True,
	email_template=None,
	communication_type=None,
	add_signature=True,
) -> dict[str, str]:
	"""Internal method to make a new communication that ignores Permission checks."""

	sender = sender or get_formatted_email(frappe.session.user)
	recipients = list_to_str(recipients) if isinstance(recipients, list) else recipients
	cc = list_to_str(cc) if isinstance(cc, list) else cc
	bcc = list_to_str(bcc) if isinstance(bcc, list) else bcc

	comm: "Communication" = frappe.get_doc(
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
		}
	)
	comm.flags.skip_add_signature = not add_signature
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
					"Unable to send mail because of a missing email account. Please setup default Email Account from Setup > Email > Email Account"
				),
				exc=frappe.OutgoingEmailError,
			)

		comm.send_email(
			print_html=print_html,
			print_format=print_format,
			send_me_a_copy=send_me_a_copy,
			print_letterhead=print_letterhead,
		)

	emails_not_sent_to = comm.exclude_emails_list(include_sender=send_me_a_copy)

	return {"name": comm.name, "emails_not_sent_to": ", ".join(emails_not_sent_to)}


def validate_email(doc: "Communication") -> None:
	"""Validate Email Addresses of Recipients and CC"""
	if (
		not (doc.communication_type == "Communication" and doc.communication_medium == "Email")
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


def add_attachments(name, attachments):
	"""Add attachments to the given Communication"""
	# loop through attachments
	for a in attachments:
		if isinstance(a, str):
			attach = frappe.db.get_value(
				"File", {"name": a}, ["file_name", "file_url", "is_private"], as_dict=1
			)
			# save attachments to new doc
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_url": attach.file_url,
					"attached_to_doctype": "Communication",
					"attached_to_name": name,
					"folder": "Home/Attachments",
					"is_private": attach.is_private,
				}
			)
			_file.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True, methods=("GET",))
def mark_email_as_seen(name: str = None):
	try:
		update_communication_as_read(name)
		frappe.db.commit()  # nosemgrep: this will be called in a GET request

	except Exception:
		frappe.log_error("Unable to mark as seen", None, "Communication", name)

	finally:
		frappe.response.update(
			{
				"type": "binary",
				"filename": "imaginary_pixel.png",
				"filecontent": (
					b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
					b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\r"
					b"IDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0"
					b"\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
				),
			}
		)


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
