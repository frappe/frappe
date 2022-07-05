# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import absolute_import, unicode_literals

import json
import time
from email.utils import formataddr

from six import string_types
from six.moves import range

import frappe
import frappe.email.smtp
from frappe import _
from frappe.core.utils import get_parent_doc
from frappe.email.email_body import get_message_id
from frappe.utils import (
	cint,
	get_datetime,
	get_formatted_email,
	get_string_between,
	get_url,
	list_to_str,
	parse_addr,
	split_emails,
	validate_email_address,
)
from frappe.utils.background_jobs import enqueue


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
):
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
		read_receipt=read_receipt,
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
):
	"""Internal method to make a new communication that ignores Permission checks."""

	sender = sender or get_formatted_email(frappe.session.user)
	recipients = list_to_str(recipients) if isinstance(recipients, list) else recipients
	cc = list_to_str(cc) if isinstance(cc, list) else cc
	bcc = list_to_str(bcc) if isinstance(bcc, list) else bcc

	comm = frappe.get_doc(
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

	if isinstance(attachments, string_types):
		attachments = json.loads(attachments)

	# if not committed, delayed task doesn't find the communication
	if attachments:
		add_attachments(comm.name, attachments)

	if cint(send_email):
		# Raise error if outgoing email account is missing
		_ = frappe.email.smtp.get_outgoing_email_account(append_to=comm.doctype, sender=comm.sender)
		frappe.flags.print_letterhead = cint(print_letterhead)
		comm.send(print_html, print_format, attachments, send_me_a_copy=send_me_a_copy)

	return {
		"name": comm.name,
		"emails_not_sent_to": ", ".join(comm.emails_not_sent_to)
		if hasattr(comm, "emails_not_sent_to")
		else None,
	}


def validate_email(doc):
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

	# validate sender


def notify(
	doc,
	print_html=None,
	print_format=None,
	attachments=None,
	recipients=None,
	cc=None,
	bcc=None,
	fetched_from_email_account=False,
):
	"""Calls a delayed task 'sendmail' that enqueus email in Email Queue queue

	:param print_html: Send given value as HTML attachment
	:param print_format: Attach print format of parent document
	:param attachments: A list of filenames that should be attached when sending this email
	:param recipients: Email recipients
	:param cc: Send email as CC to
	:param bcc: Send email as BCC to
	:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

	"""
	recipients, cc, bcc = get_recipients_cc_and_bcc(
		doc, recipients, cc, bcc, fetched_from_email_account=fetched_from_email_account
	)

	if not recipients and not cc:
		return

	doc.emails_not_sent_to = set(doc.all_email_addresses) - set(doc.sent_email_addresses)

	if frappe.flags.in_test:
		# for test cases, run synchronously
		doc._notify(
			print_html=print_html,
			print_format=print_format,
			attachments=attachments,
			recipients=recipients,
			cc=cc,
			bcc=None,
		)
	else:
		enqueue(
			sendmail,
			queue="default",
			timeout=300,
			event="sendmail",
			enqueue_after_commit=True,
			communication_name=doc.name,
			print_html=print_html,
			print_format=print_format,
			attachments=attachments,
			recipients=recipients,
			cc=cc,
			bcc=bcc,
			lang=frappe.local.lang,
			session=frappe.local.session,
			print_letterhead=frappe.flags.print_letterhead,
		)


def _notify(
	doc, print_html=None, print_format=None, attachments=None, recipients=None, cc=None, bcc=None
):

	prepare_to_notify(doc, print_html, print_format, attachments)

	if doc.outgoing_email_account.send_unsubscribe_message:
		unsubscribe_message = _("Leave this conversation")
	else:
		unsubscribe_message = ""

	frappe.sendmail(
		recipients=(recipients or []),
		cc=(cc or []),
		bcc=(bcc or []),
		expose_recipients="header",
		sender=doc.sender,
		reply_to=doc.incoming_email_account,
		subject=doc.subject,
		content=doc.content,
		reference_doctype=doc.reference_doctype,
		reference_name=doc.reference_name,
		attachments=doc.attachments,
		message_id=doc.message_id,
		unsubscribe_message=unsubscribe_message,
		delayed=True,
		communication=doc.name,
		read_receipt=doc.read_receipt,
		is_notification=True if doc.sent_or_received == "Received" else False,
		print_letterhead=frappe.flags.print_letterhead,
	)


def get_recipients_cc_and_bcc(doc, recipients, cc, bcc, fetched_from_email_account=False):
	doc.all_email_addresses = []
	doc.sent_email_addresses = []
	doc.previous_email_sender = None

	if not recipients:
		recipients = get_recipients(doc, fetched_from_email_account=fetched_from_email_account)

	if not cc:
		cc = get_cc(doc, recipients, fetched_from_email_account=fetched_from_email_account)

	if not bcc:
		bcc = get_bcc(doc, recipients, fetched_from_email_account=fetched_from_email_account)

	if fetched_from_email_account:
		# email was already sent to the original recipient by the sender's email service
		original_recipients, recipients = recipients, []

		# send email to the sender of the previous email in the thread which this email is a reply to
		# provides erratic results and can send external
		# if doc.previous_email_sender:
		# 	recipients.append(doc.previous_email_sender)

		# cc that was received in the email
		original_cc = split_emails(doc.cc)

		# don't cc to people who already received the mail from sender's email service
		cc = list(set(cc) - set(original_cc) - set(original_recipients))
		remove_administrator_from_email_list(cc)

		original_bcc = split_emails(doc.bcc)
		bcc = list(set(bcc) - set(original_bcc) - set(original_recipients))
		remove_administrator_from_email_list(bcc)

	remove_administrator_from_email_list(recipients)

	return recipients, cc, bcc


def remove_administrator_from_email_list(email_list):
	administrator_email = list(filter(lambda emails: "Administrator" in emails, email_list))
	if administrator_email:
		email_list.remove(administrator_email[0])


def prepare_to_notify(doc, print_html=None, print_format=None, attachments=None):
	"""Prepare to make multipart MIME Email

	:param print_html: Send given value as HTML attachment.
	:param print_format: Attach print format of parent document."""

	view_link = frappe.utils.cint(
		frappe.db.get_value("System Settings", "System Settings", "attach_view_link")
	)

	if print_format and view_link:
		doc.content += get_attach_link(doc, print_format)

	set_incoming_outgoing_accounts(doc)

	if not doc.sender:
		doc.sender = doc.outgoing_email_account.email_id

	if not doc.sender_full_name:
		doc.sender_full_name = doc.outgoing_email_account.name or _("Notification")

	if doc.sender:
		# combine for sending to get the format 'Jane <jane@example.com>'
		doc.sender = get_formatted_email(doc.sender_full_name, mail=doc.sender)

	doc.attachments = []

	if print_html or print_format:
		doc.attachments.append(
			{
				"print_format_attachment": 1,
				"doctype": doc.reference_doctype,
				"name": doc.reference_name,
				"print_format": print_format,
				"html": print_html,
			}
		)

	if attachments:
		if isinstance(attachments, string_types):
			attachments = json.loads(attachments)

		for a in attachments:
			if isinstance(a, string_types):
				# is it a filename?
				try:
					# check for both filename and file id
					file_id = frappe.db.get_all("File", or_filters={"file_name": a, "name": a}, limit=1)
					if not file_id:
						frappe.throw(_("Unable to find attachment {0}").format(a))
					file_id = file_id[0]["name"]
					_file = frappe.get_doc("File", file_id)
					_file.get_content()
					# these attachments will be attached on-demand
					# and won't be stored in the message
					doc.attachments.append({"fid": file_id})
				except IOError:
					frappe.throw(_("Unable to find attachment {0}").format(a))
			else:
				doc.attachments.append(a)


def set_incoming_outgoing_accounts(doc):
	doc.incoming_email_account = doc.outgoing_email_account = None

	if not doc.incoming_email_account and doc.sender:
		doc.incoming_email_account = frappe.db.get_value(
			"Email Account", {"email_id": doc.sender, "enable_incoming": 1}, "email_id"
		)

	if not doc.incoming_email_account and doc.reference_doctype:
		doc.incoming_email_account = frappe.db.get_value(
			"Email Account",
			{
				"append_to": doc.reference_doctype,
			},
			"email_id",
		)

	if not doc.incoming_email_account:
		doc.incoming_email_account = frappe.db.get_value(
			"Email Account", {"default_incoming": 1, "enable_incoming": 1}, "email_id"
		)

	doc.outgoing_email_account = frappe.email.smtp.get_outgoing_email_account(
		raise_exception_not_set=False, append_to=doc.doctype, sender=doc.sender
	)

	if doc.sent_or_received == "Sent":
		doc.db_set("email_account", doc.outgoing_email_account.name)


def get_recipients(doc, fetched_from_email_account=False):
	"""Build a list of email addresses for To"""
	# [EDGE CASE] doc.recipients can be None when an email is sent as BCC
	recipients = split_emails(doc.recipients)

	# if fetched_from_email_account and doc.in_reply_to:
	# add sender of previous reply
	# doc.previous_email_sender = frappe.db.get_value("Communication", doc.in_reply_to, "sender")
	# recipients.append(doc.previous_email_sender)

	if recipients:
		recipients = filter_email_list(doc, recipients, [])

	return recipients


def get_cc(doc, recipients=None, fetched_from_email_account=False):
	"""Build a list of email addresses for CC"""
	# get a copy of CC list
	cc = split_emails(doc.cc)

	if doc.reference_doctype and doc.reference_name:
		if fetched_from_email_account:
			# if it is a fetched email, add follows to CC
			cc.append(get_owner_email(doc))
			cc += get_assignees(doc)

	if getattr(doc, "send_me_a_copy", False) and doc.sender not in cc:
		cc.append(doc.sender)

	if cc:
		# exclude unfollows, recipients and unsubscribes
		exclude = []  # added to remove account check
		exclude += [
			d[0] for d in frappe.db.get_all("User", ["email"], {"thread_notify": 0}, as_list=True)
		]
		exclude += [(parse_addr(email)[1] or "").lower() for email in recipients]

		if fetched_from_email_account:
			# exclude sender when pulling email
			exclude += [parse_addr(doc.sender)[1]]

		if doc.reference_doctype and doc.reference_name:
			exclude += [
				d[0]
				for d in frappe.db.get_all(
					"Email Unsubscribe",
					["email"],
					{"reference_doctype": doc.reference_doctype, "reference_name": doc.reference_name},
					as_list=True,
				)
			]

		cc = filter_email_list(doc, cc, exclude, is_cc=True)

	return cc


def get_bcc(doc, recipients=None, fetched_from_email_account=False):
	"""Build a list of email addresses for BCC"""
	bcc = split_emails(doc.bcc)

	if bcc:
		exclude = []
		exclude += [
			d[0] for d in frappe.db.get_all("User", ["email"], {"thread_notify": 0}, as_list=True)
		]
		exclude += [(parse_addr(email)[1] or "").lower() for email in recipients]

		if fetched_from_email_account:
			# exclude sender when pulling email
			exclude += [parse_addr(doc.sender)[1]]

		if doc.reference_doctype and doc.reference_name:
			exclude += [
				d[0]
				for d in frappe.db.get_all(
					"Email Unsubscribe",
					["email"],
					{"reference_doctype": doc.reference_doctype, "reference_name": doc.reference_name},
					as_list=True,
				)
			]

		bcc = filter_email_list(doc, bcc, exclude, is_bcc=True)

	return bcc


def add_attachments(name, attachments):
	"""Add attachments to the given Communication"""
	# loop through attachments
	for a in attachments:
		if isinstance(a, string_types):
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


def filter_email_list(doc, email_list, exclude, is_cc=False, is_bcc=False):
	# temp variables
	filtered = []
	email_address_list = []

	for email in list(set(email_list)):
		email_address = (parse_addr(email)[1] or "").lower()
		if not email_address:
			continue

		# this will be used to eventually find email addresses that aren't sent to
		doc.all_email_addresses.append(email_address)

		if (email in exclude) or (email_address in exclude):
			continue

		if is_cc:
			is_user_enabled = frappe.db.get_value("User", email_address, "enabled")
			if is_user_enabled == 0:
				# don't send to disabled users
				continue

		if is_bcc:
			is_user_enabled = frappe.db.get_value("User", email_address, "enabled")
			if is_user_enabled == 0:
				continue

		# make sure of case-insensitive uniqueness of email address
		if email_address not in email_address_list:
			# append the full email i.e. "Human <human@example.com>"
			filtered.append(email)
			email_address_list.append(email_address)

	doc.sent_email_addresses.extend(email_address_list)

	return filtered


def get_owner_email(doc):
	owner = get_parent_doc(doc).owner
	return get_formatted_email(owner) or owner


def get_assignees(doc):
	return [
		(get_formatted_email(d.owner) or d.owner)
		for d in frappe.db.get_all(
			"ToDo",
			filters={
				"reference_type": doc.reference_doctype,
				"reference_name": doc.reference_name,
				"status": "Open",
			},
			fields=["owner"],
		)
	]


def get_attach_link(doc, print_format):
	"""Returns public link for the attachment via `templates/emails/print_link.html`."""
	return frappe.get_template("templates/emails/print_link.html").render(
		{
			"url": get_url(),
			"doctype": doc.reference_doctype,
			"name": doc.reference_name,
			"print_format": print_format,
			"key": get_parent_doc(doc).get_document_share_key(),
		}
	)


def sendmail(
	communication_name,
	print_html=None,
	print_format=None,
	attachments=None,
	recipients=None,
	cc=None,
	bcc=None,
	lang=None,
	session=None,
	print_letterhead=None,
):
	try:

		if lang:
			frappe.local.lang = lang

		if session:
			# hack to enable access to private files in PDF
			session["data"] = frappe._dict(session["data"])
			frappe.local.session.update(session)

		if print_letterhead:
			frappe.flags.print_letterhead = print_letterhead

		# upto 3 retries
		for i in range(3):
			try:
				communication = frappe.get_doc("Communication", communication_name)
				communication._notify(
					print_html=print_html,
					print_format=print_format,
					attachments=attachments,
					recipients=recipients,
					cc=cc,
					bcc=bcc,
				)

			except frappe.db.InternalError as e:
				# deadlock, try again
				if frappe.db.is_deadlocked(e):
					frappe.db.rollback()
					time.sleep(1)
					continue
				else:
					raise
			else:
				break

	except Exception:
		traceback = frappe.log_error("frappe.core.doctype.communication.email.sendmail")
		raise


@frappe.whitelist(allow_guest=True, methods=("GET",))
def mark_email_as_seen(name: str = None):
	try:
		update_communication_as_read(name)
		frappe.db.commit()  # nosemgrep: this will be called in a GET request

	except Exception:
		frappe.log_error(frappe.get_traceback())

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
