# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
import frappe
import json
from email.utils import formataddr, parseaddr
from frappe.utils import get_url, get_formatted_email, cint, validate_email_add, split_emails
from frappe.utils.file_manager import get_file
from frappe.email.bulk import check_bulk_limit
import frappe.email.smtp
from frappe import _

from frappe.model.document import Document

class Communication(Document):
	no_feed_on_delete = True

	"""Communication represents an external communication like Email."""

	def get_parent_doc(self):
		"""Returns document of `reference_doctype`, `reference_doctype`"""
		if not hasattr(self, "parent_doc"):
			if self.reference_doctype and self.reference_name:
				self.parent_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			else:
				self.parent_doc = None
		return self.parent_doc

	def validate(self):
		if self.get("__islocal"):
			if self.reference_doctype and self.reference_name:
				self.status = "Linked"
			else:
				self.status = "Open"

		# validate recipients
		for email in split_emails(self.recipients):
			validate_email_add(email, throw=True)

		# validate CC
		for email in split_emails(self.cc):
			validate_email_add(email, throw=True)

	def after_insert(self):
		# send new comment to listening clients
		comment = self.as_dict()
		comment["comment"] = comment["content"]
		comment["comment_by"] = comment["sender"]
		comment["comment_type"] = comment["communication_medium"]

		frappe.publish_realtime('new_comment', comment, doctype = self.reference_doctype,
			docname = self.reference_name)

	def on_update(self):
		"""Update parent status as `Open` or `Replied`."""
		self.update_parent()

	def update_parent(self):
		"""Update status of parent document based on who is replying."""
		parent = self.get_parent_doc()
		if not parent:
			return

		status_field = parent.meta.get_field("status")

		if status_field and "Open" in (status_field.options or "").split("\n"):
			to_status = "Open" if self.sent_or_received=="Received" else "Replied"

			if to_status in status_field.options.splitlines():
				parent.db_set("status", to_status)

		parent.notify_update()

	def send(self, print_html=None, print_format=None, attachments=None,
		send_me_a_copy=False, recipients=None):
		"""Send communication via Email.

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		self.send_me_a_copy = send_me_a_copy
		self.notify(print_html, print_format, attachments, recipients)

	def notify(self, print_html=None, print_format=None, attachments=None,
		recipients=None, cc=None, fetched_from_email_account=False):
		"""Calls a delayed celery task 'sendmail' that enqueus email in Bulk Email queue

		:param print_html: Send given value as HTML attachment
		:param print_format: Attach print format of parent document
		:param attachments: A list of filenames that should be attached when sending this email
		:param recipients: Email recipients
		:param cc: Send email as CC to
		:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

		"""
		recipients, cc = self.get_recipients_and_cc(recipients, cc,
			fetched_from_email_account=fetched_from_email_account)

		self.emails_not_sent_to = set(self.all_email_addresses) - set(self.sent_email_addresses)

		if frappe.flags.in_test:
			# for test cases, run synchronously
			self._notify(print_html=print_html, print_format=print_format, attachments=attachments,
				recipients=recipients, cc=cc)
		else:
			check_bulk_limit(list(set(self.sent_email_addresses)))

			from frappe.tasks import sendmail
			sendmail.delay(frappe.local.site, self.name,
				print_html=print_html, print_format=print_format, attachments=attachments,
				recipients=recipients, cc=cc, lang=frappe.local.lang)

	def _notify(self, print_html=None, print_format=None, attachments=None,
		recipients=None, cc=None):

		self.prepare_to_notify(print_html, print_format, attachments)

		frappe.sendmail(
			recipients=(recipients or []) + (cc or []),
			show_as_cc=(cc or []),
			expose_recipients=True,
			sender=self.sender,
			reply_to=self.incoming_email_account,
			subject=self.subject,
			content=self.content,
			reference_doctype=self.reference_doctype,
			reference_name=self.reference_name,
			attachments=self.attachments,
			message_id=self.name,
			unsubscribe_message=_("Leave this conversation"),
			bulk=True
		)

	def get_recipients_and_cc(self, recipients, cc, fetched_from_email_account=False):
		self.all_email_addresses = []
		self.sent_email_addresses = []
		self.previous_email_sender = None

		if not recipients:
			recipients = self.get_recipients(fetched_from_email_account=fetched_from_email_account)

		if not cc:
			cc = self.get_cc(recipients, fetched_from_email_account=fetched_from_email_account)

		if fetched_from_email_account:
			# email was already sent to the original recipient by the sender's email service
			original_recipients, recipients = recipients, []

			# send email to the sender of the previous email in the thread which this email is a reply to
			if self.previous_email_sender:
				recipients.append(self.previous_email_sender)

			# cc that was received in the email
			original_cc = split_emails(self.cc)

			# don't cc to people who already received the mail from sender's email service
			cc = list(set(cc) - set(original_cc) - set(original_recipients))

		return recipients, cc

	def prepare_to_notify(self, print_html=None, print_format=None, attachments=None):
		"""Prepare to make multipart MIME Email

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		if print_format:
			self.content += self.get_attach_link(print_format)

		self.set_incoming_outgoing_accounts()

		if not self.sender or cint(self.outgoing_email_account.always_use_account_email_id_as_sender):
			self.sender = formataddr([frappe.session.data.full_name or "Notification", self.outgoing_email_account.email_id])

		self.attachments = []

		if print_html or print_format:
			self.attachments.append(frappe.attach_print(self.reference_doctype, self.reference_name,
				print_format=print_format, html=print_html))

		if attachments:
			if isinstance(attachments, basestring):
				attachments = json.loads(attachments)

			for a in attachments:
				if isinstance(a, basestring):
					# is it a filename?
					try:
						file = get_file(a)
						self.attachments.append({"fname": file[0], "fcontent": file[1]})
					except IOError:
						frappe.throw(_("Unable to find attachment {0}").format(a))
				else:
					self.attachments.append(a)

	def set_incoming_outgoing_accounts(self):
		self.incoming_email_account = self.outgoing_email_account = None

		if self.reference_doctype:
			self.incoming_email_account = frappe.db.get_value("Email Account",
				{"append_to": self.reference_doctype, "enable_incoming": 1}, "email_id")

			self.outgoing_email_account = frappe.db.get_value("Email Account",
				{"append_to": self.reference_doctype, "enable_outgoing": 1},
				["email_id", "always_use_account_email_id_as_sender"], as_dict=True)

		if not self.incoming_email_account:
			self.incoming_email_account = frappe.db.get_value("Email Account",
				{"default_incoming": 1, "enable_incoming": 1},  "email_id")

		if not self.outgoing_email_account:
			self.outgoing_email_account = frappe.db.get_value("Email Account",
				{"default_outgoing": 1, "enable_outgoing": 1},
				["email_id", "always_use_account_email_id_as_sender"], as_dict=True) or frappe._dict()

	def get_recipients(self, fetched_from_email_account=False):
		"""Build a list of email addresses for To"""
		# [EDGE CASE] self.recipients can be None when an email is sent as BCC
		recipients = split_emails(self.recipients)

		if fetched_from_email_account and self.in_reply_to:
			# add sender of previous reply
			self.previous_email_sender = frappe.db.get_value("Communication", self.in_reply_to, "sender")
			recipients.append(self.previous_email_sender)

		if recipients:
			# exclude email accounts
			exclude = [d[0] for d in
				frappe.db.get_all("Email Account", ["email_id"], {"enable_incoming": 1}, as_list=True)]
			exclude += [d[0] for d in
				frappe.db.get_all("Email Account", ["login_id"], {"enable_incoming": 1}, as_list=True)
				if d[0]]

			recipients = self.filter_email_list(recipients, exclude)

		return recipients

	def get_cc(self, recipients=None, fetched_from_email_account=False):
		"""Build a list of email addresses for CC"""
		# get a copy of CC list
		cc = split_emails(self.cc)

		if self.reference_doctype and self.reference_name:
			if fetched_from_email_account:
				# if it is a fetched email, add follows to CC
				cc.append(self.get_owner_email())
				cc += self.get_assignees()
				cc += self.get_starrers()

		if cc:
			# exclude email accounts, unfollows, recipients and unsubscribes
			exclude = [d[0] for d in
				frappe.db.get_all("Email Account", ["email_id"], {"enable_incoming": 1}, as_list=True)]
			exclude += [d[0] for d in
				frappe.db.get_all("Email Account", ["login_id"], {"enable_incoming": 1}, as_list=True)
				if d[0]]
			exclude += [d[0] for d in frappe.db.get_all("User", ["name"], {"thread_notify": 0}, as_list=True)]
			exclude += [(parseaddr(email)[1] or "").lower() for email in recipients]

			if fetched_from_email_account:
				# exclude sender when pulling email
				exclude += [parseaddr(self.sender)[1]]

			if self.reference_doctype and self.reference_name:
				exclude += [d[0] for d in frappe.db.get_all("Email Unsubscribe", ["email"],
					{"reference_doctype": self.reference_doctype, "reference_name": self.reference_name}, as_list=True)]

			cc = self.filter_email_list(cc, exclude, is_cc=True)

		if getattr(self, "send_me_a_copy", False) and self.sender not in cc:
			self.all_email_addresses.append((parseaddr(self.sender)[1] or "").lower())
			cc.append(self.sender)

		return cc

	def filter_email_list(self, email_list, exclude, is_cc=False):
		# temp variables
		filtered = []
		email_address_list = []

		for email in list(set(email_list)):
			email_address = (parseaddr(email)[1] or "").lower()
			if not email_address:
				continue

			# this will be used to eventually find email addresses that aren't sent to
			self.all_email_addresses.append(email_address)

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

		self.sent_email_addresses.extend(email_address_list)

		return filtered

	def get_starrers(self):
		"""Return list of users who have starred this document."""
		return [( get_formatted_email(user) or user ) for user in self.get_parent_doc().get_starred_by()]

	def get_owner_email(self):
		owner = self.get_parent_doc().owner
		return get_formatted_email(owner) or owner

	def get_assignees(self):
		return [( get_formatted_email(d.owner) or d.owner ) for d in
			frappe.db.get_all("ToDo", filters={
				"reference_type": self.reference_doctype,
				"reference_name": self.reference_name,
				"status": "Open"
			}, fields=["owner"])
		]

	def get_attach_link(self, print_format):
		"""Returns public link for the attachment via `templates/emails/print_link.html`."""
		return frappe.get_template("templates/emails/print_link.html").render({
			"url": get_url(),
			"doctype": self.reference_doctype,
			"name": self.reference_name,
			"print_format": print_format,
			"key": self.get_parent_doc().get_signature()
		})

def on_doctype_update():
	"""Add index in `tabCommunication` for `(reference_doctype, reference_name)`"""
	frappe.db.add_index("Communication", ["reference_doctype", "reference_name"])

@frappe.whitelist()
def make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', ignore_doctype_permissions=False,
	send_me_a_copy=False, cc=None):
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

	if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name) and not ignore_doctype_permissions:
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	if not sender:
		sender = get_formatted_email(frappe.session.user)

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"recipients": recipients,
		"cc": cc or None,
		"communication_medium": communication_medium,
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name
	})
	comm.insert(ignore_permissions=True)

	# needed for communication.notify which uses celery delay
	# if not committed, delayed task doesn't find the communication
	frappe.db.commit()

	if send_email:
		comm.send_me_a_copy = send_me_a_copy
		comm.send(print_html, print_format, attachments, send_me_a_copy=send_me_a_copy)

	return {
		"name": comm.name,
		"emails_not_sent_to": ", ".join(comm.emails_not_sent_to) if hasattr(comm, "emails_not_sent_to") else None
	}

@frappe.whitelist()
def get_convert_to():
	return frappe.get_hooks("communication_convert_to")
