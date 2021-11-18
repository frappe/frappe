# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import json
from email.utils import formataddr
from frappe.core.utils import get_parent_doc
from frappe.utils import (get_url, get_formatted_email, cint, list_to_str,
	validate_email_address, split_emails, parse_addr, get_datetime)
from frappe.email.email_body import get_message_id
import frappe.email.smtp
import time
from frappe import _
from frappe.utils.background_jobs import enqueue

OUTGOING_EMAIL_ACCOUNT_MISSING = _("""
	Unable to send mail because of a missing email account.
	Please setup default Email Account from Setup > Email > Email Account
""")

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, sender_full_name=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, cc=None, bcc=None,
	flags=None, read_receipt=None, print_letterhead=True, email_template=None, communication_type=None,
	ignore_permissions=False):
	"""Make a new communication.

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
	is_error_report = (doctype=="User" and name==frappe.session.user and subject=="Error Report")
	send_me_a_copy = cint(send_me_a_copy)

	if not ignore_permissions:
		if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name) and not (flags or {}).get('ignore_doctype_permissions'):
			raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
				doctype=doctype, name=name))

	if not sender:
		sender = get_formatted_email(frappe.session.user)

	recipients = list_to_str(recipients) if isinstance(recipients, list) else recipients
	cc = list_to_str(cc) if isinstance(cc, list) else cc
	bcc = list_to_str(bcc) if isinstance(bcc, list) else bcc

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"sender_full_name":sender_full_name,
		"recipients": recipients,
		"cc": cc or None,
		"bcc": bcc or None,
		"communication_medium": communication_medium,
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name,
		"email_template": email_template,
		"message_id":get_message_id().strip(" <>"),
		"read_receipt":read_receipt,
		"has_attachment": 1 if attachments else 0,
		"communication_type": communication_type
	}).insert(ignore_permissions=True)

	comm.save(ignore_permissions=True)

	if isinstance(attachments, str):
		attachments = json.loads(attachments)

	# if not committed, delayed task doesn't find the communication
	if attachments:
		add_attachments(comm.name, attachments)

	if cint(send_email):
		if not comm.get_outgoing_email_account():
			frappe.throw(msg=OUTGOING_EMAIL_ACCOUNT_MISSING, exc=frappe.OutgoingEmailError)

		comm.send_email(print_html=print_html, print_format=print_format,
			send_me_a_copy=send_me_a_copy, print_letterhead=print_letterhead)

	emails_not_sent_to = comm.exclude_emails_list(include_sender=send_me_a_copy)
	return {
		"name": comm.name,
		"emails_not_sent_to": ", ".join(emails_not_sent_to or [])
	}

def validate_email(doc):
	"""Validate Email Addresses of Recipients and CC"""
	if not (doc.communication_type=="Communication" and doc.communication_medium == "Email") or doc.flags.in_receive:
		return

	# validate recipients
	for email in split_emails(doc.recipients):
		validate_email_address(email, throw=True)

	# validate CC
	for email in split_emails(doc.cc):
		validate_email_address(email, throw=True)

	for email in split_emails(doc.bcc):
		validate_email_address(email, throw=True)

	# validate sender

def set_incoming_outgoing_accounts(doc):
	from frappe.email.doctype.email_account.email_account import EmailAccount
	incoming_email_account = EmailAccount.find_incoming(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype)
	doc.incoming_email_account = incoming_email_account.email_id if incoming_email_account else None

	doc.outgoing_email_account = EmailAccount.find_outgoing(
		match_by_email=doc.sender, match_by_doctype=doc.reference_doctype)

	if doc.sent_or_received == "Sent":
		doc.db_set("email_account", doc.outgoing_email_account.name)

def add_attachments(name, attachments):
	'''Add attachments to the given Communication'''
	# loop through attachments
	for a in attachments:
		if isinstance(a, str):
			attach = frappe.db.get_value("File", {"name":a},
				["file_name", "file_url", "is_private"], as_dict=1)
			# save attachments to new doc
			_file = frappe.get_doc({
				"doctype": "File",
				"file_url": attach.file_url,
				"attached_to_doctype": "Communication",
				"attached_to_name": name,
				"folder": "Home/Attachments",
				"is_private": attach.is_private
			})
			_file.save(ignore_permissions=True)

@frappe.whitelist(allow_guest=True, methods=("GET",))
def mark_email_as_seen(name: str = None):
	try:
		update_communication_as_read(name)
		frappe.db.commit()  # nosemgrep: this will be called in a GET request

	except Exception:
		frappe.log_error(frappe.get_traceback())

	finally:
		frappe.response.update({
			"type": "binary",
			"filename": "imaginary_pixel.png",
			"filecontent": (
				b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
				b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\r"
				b"IDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0"
				b"\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
			)
		})

def update_communication_as_read(name):
	if not name or not isinstance(name, str):
		return

	communication = frappe.db.get_value(
		"Communication",
		name,
		"read_by_recipient",
		as_dict=True
	)

	if not communication or communication.read_by_recipient:
		return

	frappe.db.set_value("Communication", name, {
		"read_by_recipient": 1,
		"delivery_status": "Read",
		"read_by_recipient_on": get_datetime()
	})
