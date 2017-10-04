# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
from six.moves import range
from six import string_types
import frappe
import json
from email.utils import formataddr
from frappe.utils import (get_url, get_formatted_email, cint,
	validate_email_add, split_emails, time_diff_in_seconds, parse_addr)
from frappe.utils.file_manager import get_file
from frappe.email.queue import check_email_limit
from frappe.utils.scheduler import log
from frappe.email.email_body import get_message_id
import frappe.email.smtp
import MySQLdb
import time
from frappe import _
from frappe.utils.background_jobs import enqueue

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, sender_full_name=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, cc=None, flags=None,read_receipt=None):
	"""Make a new communication.

	:param doctype: Reference DocType.
	:param name: Reference Document name.
	:param content: Communication body.
	:param subject: Communication subject.
	:param sent_or_received: Sent or Received (default **Sent**).
	:param sender: Communcation sender (default current user).
	:param recipients: Communication recipients as list.
	:param communication_medium: Medium of communication (default **Email**).
	:param send_mail: Send via email (default **False**).
	:param print_html: HTML Print format to be sent as attachment.
	:param print_format: Print Format name of parent document to be sent as attachment.
	:param attachments: List of attachments as list of files or JSON string.
	:param send_me_a_copy: Send a copy to the sender (default **False**).
	"""

	is_error_report = (doctype=="User" and name==frappe.session.user and subject=="Error Report")
	send_me_a_copy = cint(send_me_a_copy)

	if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name) and not (flags or {}).get('ignore_doctype_permissions'):
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	if not sender:
		sender = get_formatted_email(frappe.session.user)

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"sender_full_name":sender_full_name,
		"recipients": recipients,
		"cc": cc or None,
		"communication_medium": communication_medium,
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name,
		"message_id":get_message_id().strip(" <>"),
		"read_receipt":read_receipt,
		"has_attachment": 1 if attachments else 0
	})
	comm.insert(ignore_permissions=True)

	if not doctype:
		# if no reference given, then send it against the communication
		comm.db_set(dict(reference_doctype='Communication', reference_name=comm.name))

	if isinstance(attachments, string_types):
		attachments = json.loads(attachments)

	# if not committed, delayed task doesn't find the communication
	if attachments:
		add_attachments(comm.name, attachments)

	frappe.db.commit()

	if cint(send_email):
		comm.send(print_html, print_format, attachments, send_me_a_copy=send_me_a_copy)

	return {
		"name": comm.name,
		"emails_not_sent_to": ", ".join(comm.emails_not_sent_to) if hasattr(comm, "emails_not_sent_to") else None
	}

def validate_email(doc):
	"""Validate Email Addresses of Recipients and CC"""
	if not (doc.communication_type=="Communication" and doc.communication_medium == "Email") or doc.flags.in_receive:
		return

	# validate recipients
	for email in split_emails(doc.recipients):
		validate_email_add(email, throw=True)

	# validate CC
	for email in split_emails(doc.cc):
		validate_email_add(email, throw=True)

	# validate sender

def notify(doc, print_html=None, print_format=None, attachments=None,
	recipients=None, cc=None, fetched_from_email_account=False):
	"""Calls a delayed task 'sendmail' that enqueus email in Email Queue queue

	:param print_html: Send given value as HTML attachment
	:param print_format: Attach print format of parent document
	:param attachments: A list of filenames that should be attached when sending this email
	:param recipients: Email recipients
	:param cc: Send email as CC to
	:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

	"""
	recipients, cc = get_recipients_and_cc(doc, recipients, cc,
		fetched_from_email_account=fetched_from_email_account)

	if not recipients:
		return

	doc.emails_not_sent_to = set(doc.all_email_addresses) - set(doc.sent_email_addresses)

	if frappe.flags.in_test:
		# for test cases, run synchronously
		doc._notify(print_html=print_html, print_format=print_format, attachments=attachments,
			recipients=recipients, cc=cc)
	else:
		check_email_limit(list(set(doc.sent_email_addresses)))
		enqueue(sendmail, queue="default", timeout=300, event="sendmail",
			communication_name=doc.name,
			print_html=print_html, print_format=print_format, attachments=attachments,
			recipients=recipients, cc=cc, lang=frappe.local.lang, session=frappe.local.session)

def _notify(doc, print_html=None, print_format=None, attachments=None,
	recipients=None, cc=None):

	prepare_to_notify(doc, print_html, print_format, attachments)

	if doc.outgoing_email_account.send_unsubscribe_message:
		unsubscribe_message = _("Leave this conversation")
	else:
		unsubscribe_message = ""

	frappe.sendmail(
		recipients=(recipients or []),
		cc=(cc or []),
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
		is_notification=True if doc.sent_or_received =="Received" else False
	)

def update_parent_status(doc):
	"""Update status of parent document based on who is replying."""
	parent = doc.get_parent_doc()
	if not parent:
		return

	# update parent status only if we create the Email communication
	# ignore in case of only Comment is added
	if doc.communication_type == "Comment":
		return

	status_field = parent.meta.get_field("status")

	if status_field:
		options = (status_field.options or '').splitlines()

		# if status has a "Replied" option, then update the status
		if 'Replied' in options:
			to_status = "Open" if doc.sent_or_received=="Received" else "Replied"

			if to_status in options:
				parent.db_set("status", to_status)

	update_mins_to_first_communication(parent, doc)
	parent.run_method('notify_communication', doc)

	parent.notify_update()

def get_recipients_and_cc(doc, recipients, cc, fetched_from_email_account=False):
	doc.all_email_addresses = []
	doc.sent_email_addresses = []
	doc.previous_email_sender = None

	if not recipients:
		recipients = get_recipients(doc, fetched_from_email_account=fetched_from_email_account)

	if not cc:
		cc = get_cc(doc, recipients, fetched_from_email_account=fetched_from_email_account)

	if fetched_from_email_account:
		# email was already sent to the original recipient by the sender's email service
		original_recipients, recipients = recipients, []

		# send email to the sender of the previous email in the thread which this email is a reply to
		#provides erratic results and can send external
		#if doc.previous_email_sender:
		#	recipients.append(doc.previous_email_sender)

		# cc that was received in the email
		original_cc = split_emails(doc.cc)

		# don't cc to people who already received the mail from sender's email service
		cc = list(set(cc) - set(original_cc) - set(original_recipients))

	if 'Administrator' in recipients:
		recipients.remove('Administrator')

	return recipients, cc

def prepare_to_notify(doc, print_html=None, print_format=None, attachments=None):
	"""Prepare to make multipart MIME Email

	:param print_html: Send given value as HTML attachment.
	:param print_format: Attach print format of parent document."""

	view_link = frappe.utils.cint(frappe.db.get_value("Print Settings", "Print Settings", "attach_view_link"))

	if print_format and view_link:
		doc.content += get_attach_link(doc, print_format)

	set_incoming_outgoing_accounts(doc)

	if not doc.sender:
		doc.sender = doc.outgoing_email_account.email_id

	if not doc.sender_full_name:
		doc.sender_full_name = doc.outgoing_email_account.name or _("Notification")

	if doc.sender:
		# combine for sending to get the format 'Jane <jane@example.com>'
		doc.sender = formataddr([doc.sender_full_name, doc.sender])

	doc.attachments = []

	if print_html or print_format:
		doc.attachments.append(frappe.attach_print(doc.reference_doctype, doc.reference_name,
			print_format=print_format, html=print_html))

	if attachments:
		if isinstance(attachments, string_types):
			attachments = json.loads(attachments)

		for a in attachments:
			if isinstance(a, string_types):
				# is it a filename?
				try:
					file = get_file(a)
					doc.attachments.append({"fname": file[0], "fcontent": file[1]})
				except IOError:
					frappe.throw(_("Unable to find attachment {0}").format(a))
			else:
				doc.attachments.append(a)

def set_incoming_outgoing_accounts(doc):
	doc.incoming_email_account = doc.outgoing_email_account = None

	if not doc.incoming_email_account and doc.sender:
		doc.incoming_email_account = frappe.db.get_value("Email Account",
			{"email_id": doc.sender, "enable_incoming": 1}, "email_id")

	if not doc.incoming_email_account and doc.reference_doctype:
		doc.incoming_email_account = frappe.db.get_value("Email Account",
			{"append_to": doc.reference_doctype, }, "email_id")

		doc.outgoing_email_account = frappe.db.get_value("Email Account",
			{"append_to": doc.reference_doctype, "enable_outgoing": 1},
			["email_id", "always_use_account_email_id_as_sender", "name"], as_dict=True)

	if not doc.incoming_email_account:
		doc.incoming_email_account = frappe.db.get_value("Email Account",
			{"default_incoming": 1, "enable_incoming": 1},  "email_id")

	if not doc.outgoing_email_account:
		doc.outgoing_email_account = frappe.db.get_value("Email Account",
			{"default_outgoing": 1, "enable_outgoing": 1},
			["email_id", "always_use_account_email_id_as_sender", "name", "send_unsubscribe_message"],as_dict=True) or frappe._dict()

	if not doc.outgoing_email_account:
		# if from address is not the default email account
		doc.outgoing_email_account = frappe.db.get_value("Email Account",
			{"email_id": doc.sender, "enable_outgoing": 1},
			["email_id", "always_use_account_email_id_as_sender", "name", "send_unsubscribe_message"], as_dict=True) or frappe._dict()

	if doc.sent_or_received == "Sent":
		doc.db_set("email_account", doc.outgoing_email_account.name)

def get_recipients(doc, fetched_from_email_account=False):
	"""Build a list of email addresses for To"""
	# [EDGE CASE] doc.recipients can be None when an email is sent as BCC
	recipients = split_emails(doc.recipients)

	#if fetched_from_email_account and doc.in_reply_to:
		# add sender of previous reply
		#doc.previous_email_sender = frappe.db.get_value("Communication", doc.in_reply_to, "sender")
		#recipients.append(doc.previous_email_sender)

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
		exclude = [] #added to remove account check
		exclude += [d[0] for d in frappe.db.get_all("User", ["name"], {"thread_notify": 0}, as_list=True)]
		exclude += [(parse_addr(email)[1] or "").lower() for email in recipients]

		if fetched_from_email_account:
			# exclude sender when pulling email
			exclude += [parse_addr(doc.sender)[1]]

		if doc.reference_doctype and doc.reference_name:
			exclude += [d[0] for d in frappe.db.get_all("Email Unsubscribe", ["email"],
				{"reference_doctype": doc.reference_doctype, "reference_name": doc.reference_name}, as_list=True)]

		cc = filter_email_list(doc, cc, exclude, is_cc=True)

	return cc


def add_attachments(name, attachments):
	'''Add attachments to the given Communiction'''
	from frappe.utils.file_manager import save_url

	# loop through attachments
	for a in attachments:
		if isinstance(a, string_types):
			attach = frappe.db.get_value("File", {"name":a},
				["file_name", "file_url", "is_private"], as_dict=1)

			# save attachments to new doc
			save_url(attach.file_url, attach.file_name, "Communication", name,
				"Home/Attachments", attach.is_private)

def filter_email_list(doc, email_list, exclude, is_cc=False):
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
			if is_user_enabled==0:
				# don't send to disabled users
				continue

		# make sure of case-insensitive uniqueness of email address
		if email_address not in email_address_list:
			# append the full email i.e. "Human <human@example.com>"
			filtered.append(email)
			email_address_list.append(email_address)

	doc.sent_email_addresses.extend(email_address_list)

	return filtered

def get_owner_email(doc):
	owner = doc.get_parent_doc().owner
	return get_formatted_email(owner) or owner

def get_assignees(doc):
	return [( get_formatted_email(d.owner) or d.owner ) for d in
		frappe.db.get_all("ToDo", filters={
			"reference_type": doc.reference_doctype,
			"reference_name": doc.reference_name,
			"status": "Open"
		}, fields=["owner"])
	]

def get_attach_link(doc, print_format):
	"""Returns public link for the attachment via `templates/emails/print_link.html`."""
	return frappe.get_template("templates/emails/print_link.html").render({
		"url": get_url(),
		"doctype": doc.reference_doctype,
		"name": doc.reference_name,
		"print_format": print_format,
		"key": doc.get_parent_doc().get_signature()
	})

def sendmail(communication_name, print_html=None, print_format=None, attachments=None,
	recipients=None, cc=None, lang=None, session=None):
	try:

		if lang:
			frappe.local.lang = lang

		if session:
			# hack to enable access to private files in PDF
			session['data'] = frappe._dict(session['data'])
			frappe.local.session.update(session)

		# upto 3 retries
		for i in range(3):
			try:
				communication = frappe.get_doc("Communication", communication_name)
				communication._notify(print_html=print_html, print_format=print_format, attachments=attachments,
					recipients=recipients, cc=cc)

			except MySQLdb.OperationalError as e:
				# deadlock, try again
				if e.args[0]==1213:
					frappe.db.rollback()
					time.sleep(1)
					continue
				else:
					raise
			else:
				break

	except:
		traceback = log("frappe.core.doctype.communication.email.sendmail", frappe.as_json({
			"communication_name": communication_name,
			"print_html": print_html,
			"print_format": print_format,
			"attachments": attachments,
			"recipients": recipients,
			"cc": cc,
			"lang": lang
		}))
		frappe.logger(__name__).error(traceback)
		raise

def update_mins_to_first_communication(parent, communication):
	if parent.meta.has_field('mins_to_first_response') and not parent.get('mins_to_first_response'):
		if frappe.db.get_all('User', filters={'email': communication.sender,
			'user_type': 'System User', 'enabled': 1}, limit=1):
			first_responded_on = communication.creation
			if parent.meta.has_field('first_responded_on'):
				parent.db_set('first_responded_on', first_responded_on)
			parent.db_set('mins_to_first_response', round(time_diff_in_seconds(first_responded_on, parent.creation) / 60), 2)
