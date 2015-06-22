# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
import frappe
import json
from email.utils import formataddr, parseaddr
from frappe.utils import get_url, get_formatted_email, cstr, cint
from frappe.utils.file_manager import get_file
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
				frappe.db.set_value(parent.doctype, parent.name, "status", to_status)

	def send(self, print_html=None, print_format=None, attachments=None,
		send_me_a_copy=False, recipients=None):
		"""Send communication via Email.

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		self.send_me_a_copy = send_me_a_copy
		self.notify(print_html, print_format, attachments, recipients)

	def set_incoming_outgoing_accounts(self):
		self.incoming_email_account = self.outgoing_email_account = None

		if self.reference_doctype:
			self.incoming_email_account = frappe.db.get_value("Email Account",
				{"append_to": self.reference_doctype, "enable_incoming": 1}, "email_id")

			self.outgoing_email_account = frappe.db.get_value("Email Account",
				{"append_to": self.reference_doctype, "enable_outgoing": 1},
				["email_id", "always_use_account_email_id_as_sender"], as_dict=True)

		if not self.incoming_email_account:
			self.incoming_email_account = frappe.db.get_value("Email Account", {"default_incoming": 1}, "email_id")

		if not self.outgoing_email_account:
			self.outgoing_email_account = frappe.db.get_value("Email Account", {"default_outgoing": 1},
				["email_id", "always_use_account_email_id_as_sender"], as_dict=True) or frappe._dict()

	def notify(self, print_html=None, print_format=None, attachments=None, recipients=None, except_recipient=False):
		self.prepare_to_notify(print_html, print_format, attachments)
		if not recipients:
			recipients = self.get_recipients(except_recipient=except_recipient)

		frappe.sendmail(
			recipients=recipients,
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

	def get_recipients(self, except_recipient=False):
		"""Build a list of users to which this email should go to"""
		# [EDGE CASE] self.recipients can be None when an email is sent as BCC
		original_recipients = [s.strip() for s in cstr(self.recipients).split(",")]
		recipients = original_recipients[:]

		if self.reference_doctype and self.reference_name:
			recipients += self.get_earlier_participants()
			recipients += self.get_commentors()
			recipients += self.get_assignees()
			recipients += self.get_starrers()

		# remove unsubscribed recipients
		unsubscribed = [d[0] for d in frappe.db.get_all("User", ["name"], {"thread_notify": 0}, as_list=True)]
		email_accounts = [d[0] for d in frappe.db.get_all("Email Account", ["email_id"], {"enable_incoming": 1}, as_list=True)]
		sender = parseaddr(self.sender)[1]

		filtered = []
		for e in list(set(recipients)):
			if (e=="Administrator") or ((e==self.sender) and (e not in original_recipients)) or \
				(e in unsubscribed) or (e in email_accounts):
				continue

			email_id = parseaddr(e)[1]
			if email_id==sender or email_id in unsubscribed or email_id in email_accounts:
				continue

			if except_recipient and (e==self.recipients or email_id==self.recipients):
				# while pulling email, don't send email to current recipient
				continue

			if e not in filtered and email_id not in filtered:
				filtered.append(e)

		if getattr(self, "send_me_a_copy", False):
			filtered.append(self.sender)

		return filtered

	def get_starrers(self):
		"""Return list of users who have starred this document."""
		if self.reference_doctype and self.reference_name:
			return self.get_parent_doc().get_starred_by()
		else:
			return []

	def get_earlier_participants(self):
		return frappe.db.sql_list("""
			select distinct sender
			from tabCommunication where
			reference_doctype=%s and reference_name=%s""",
				(self.reference_doctype, self.reference_name))

	def get_commentors(self):
		return frappe.db.sql_list("""
			select distinct comment_by
			from tabComment where
			comment_doctype=%s and comment_docname=%s and
			ifnull(unsubscribed, 0)=0 and comment_by!='Administrator'""",
				(self.reference_doctype, self.reference_name))

	def get_assignees(self):
		return [d.owner for d in frappe.db.get_all("ToDo", filters={"reference_type": self.reference_doctype,
			"reference_name": self.reference_name, "status": "Open"}, fields=["owner"])]

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
	send_me_a_copy=False):
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

	if not sender and frappe.session.user != "Administrator":
		sender = get_formatted_email(frappe.session.user)

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender,
		"recipients": recipients,
		"communication_medium": "Email",
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name
	})
	comm.insert(ignore_permissions=True)
	
	recipients = None
	if send_email:
		comm.send_me_a_copy = send_me_a_copy
		recipients = comm.get_recipients()
		comm.send(print_html, print_format, attachments, send_me_a_copy=send_me_a_copy, recipients=recipients)

	return {
		"name": comm.name,
		"recipients": ", ".join(recipients) if recipients else None
	}

@frappe.whitelist()
def get_convert_to():
	return frappe.get_hooks("communication_convert_to")
