# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils import get_url, cint, scrub_urls, get_formatted_email
from frappe.email.email_body import get_email
import frappe.email.smtp
from frappe import _

from frappe.model.document import Document

class Communication(Document):
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

	def send(self, print_html=None, print_format=None,
		attachments=None):
		"""Send communication via Email.

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		self.notify(self.get_email(print_html, print_format, attachments))

	def get_email(self, print_html=None, print_format=None, attachments=None):
		"""Make multipart MIME Email

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		if print_format:
			self.content += self.get_attach_link(print_format)

		default_incoming = frappe.db.get_value("Email Account", {"default_incoming": 1}, "email_id")
		default_outgoing = frappe.db.get_value("Email Account", {"default_outgoing": 1}, "email_id")

		if not self.sender:
			self.sender = "{0} <{1}>".format(frappe.session.data.full_name or "Notification", default_outgoing)

		mail = get_email(self.recipients, sender=self.sender, subject=self.subject,
			content=self.content, reply_to=default_incoming)

		mail.set_message_id(self.name)

		if print_html or print_format:
			attach_print(mail, self.get_parent_doc(), print_html, print_format)

		if isinstance(attachments, basestring):
			attachments = json.loads(attachments)

		if attachments:
			for a in attachments:
				try:
					mail.attach_file(a)
				except IOError:
					frappe.throw(_("Unable to find attachment {0}").format(a))

		return mail

	def add_to_mail_queue(self, mail):
		mail = frappe.get_doc({
			"doctype": "Bulk Email",
			"sender": mail.sender,
			"recipient": mail.recipients[0],
			"message": mail.as_string(),
			"ref_doctype": self.reference_doctype,
			"ref_docname": self.reference_name
		}).insert(ignore_permissions=True)

	def notify(self, mail, except_sender=False):
		for recipient in self.get_recipients():
			if except_sender and recipient == self.sender:
				continue
			mail.recipients = [recipient]
			self.add_to_mail_queue(mail)

	def get_recipients(self):
		# Earlier repliers
		recipients = frappe.db.sql_list("""
			select distinct sender
			from tabCommunication where
			reference_doctype=%s and reference_name=%s""",
				(self.reference_doctype, self.reference_name))

		# Commentors
		recipients += frappe.db.sql_list("""
			select distinct comment_by
			from tabComment where
			comment_doctype=%s and comment_docname=%s and
			ifnull(unsubscribed, 0)=0 and comment_by!='Administrator'""",
				(self.reference_doctype, self.reference_name))

		# Explicit recipients
		recipients += [s.strip() for s in self.recipients.split(",")]

		# Assigned
		assigned = frappe.db.get_value("ToDo", {"reference_type": self.reference_doctype,
			"reference_name": self.reference_name, "status": "Open"}, "owner")
		if assigned:
			recipients.append(assigned)

		recipients = filter(lambda e: e and e!="Administrator", list(set(recipients)))

		return recipients

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
	print_html=None, print_format=None, attachments='[]', ignore_doctype_permissions=False):
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
	:param attachments: List of attachments as list of files or JSON string."""

	is_error_report = (doctype=="User" and name==frappe.session.user and subject=="Error Report")

	if doctype and name and not is_error_report and not frappe.has_permission(doctype, "email", name) and not ignore_doctype_permissions:
		raise frappe.PermissionError("You are not allowed to send emails related to: {doctype} {name}".format(
			doctype=doctype, name=name))

	comm = frappe.get_doc({
		"doctype":"Communication",
		"subject": subject,
		"content": content,
		"sender": sender or get_formatted_email(frappe.session.user),
		"recipients": recipients,
		"communication_medium": "Email",
		"sent_or_received": sent_or_received,
		"reference_doctype": doctype,
		"reference_name": name
	})
	comm.insert(ignore_permissions=True)

	if send_email:
		comm.send(print_html, print_format, attachments)

	return comm.name

def attach_print(mail, parent_doc, print_html, print_format):
	name = parent_doc.name if parent_doc else "attachment"
	if (not print_html) and parent_doc and print_format:
		print_html = frappe.get_print(parent_doc.doctype, parent_doc.name, print_format)

	print_settings = frappe.db.get_singles_dict("Print Settings")
	send_print_as_pdf = cint(print_settings.send_print_as_pdf)

	if send_print_as_pdf:
		try:
			mail.add_pdf_attachment(name.replace(' ','').replace('/','-') + '.pdf', print_html)
		except Exception:
			frappe.msgprint(_("Error generating PDF, attachment sent as HTML"))
			frappe.errprint(frappe.get_traceback())
			send_print_as_pdf = 0

	if not send_print_as_pdf:
		print_html = scrub_urls(print_html)
		mail.add_attachment(name.replace(' ','').replace('/','-') + '.html',
			print_html, 'text/html')

@frappe.whitelist()
def get_convert_to():
	return frappe.get_hooks("communication_convert_to")
