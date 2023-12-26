# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

import frappe
import frappe.email.smtp
from frappe import _
from frappe.communications.interfaces import NotificationHandler, OutgoingCommunicationHandler
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.core.utils import get_parent_doc
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled_for_type,
)
from frappe.desk.doctype.todo.todo import ToDo
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.email_body import get_message_id
from frappe.utils import (
	cint,
	get_datetime,
	get_formatted_email,
	get_imaginary_pixel_response,
	get_string_between,
	get_url,
	list_to_str,
	parse_addr,
	split_emails,
	validate_email_address,
)

if TYPE_CHECKING:
	from frappe.communications.doctype.communication.communication import Communication
	from frappe.communications.doctype.notification.notification import Notification
	from frappe.model.document import Document


def get_assignees(doc):
	assignees = []
	assignees = frappe.get_all(
		"ToDo",
		filters={"status": "Open", "reference_name": doc.name, "reference_type": doc.doctype},
		fields=["allocated_to"],
	)

	return [d.allocated_to for d in assignees]


def get_emails_from_template(template, context):
	if not template:
		return ()

	emails = frappe.render_template(template, context) if "{" in template else template
	return filter(None, emails.replace(",", "\n").split("\n"))


def get_list_of_recipients(self, doc, context):
	recipients = []
	cc = []
	bcc = []
	for recipient in self.recipients:
		if not recipient.should_receive(context):
			continue
		if recipient.receiver_by_document_field:
			fields = recipient.receiver_by_document_field.split(",")
			# fields from child table
			if len(fields) > 1:
				for d in doc.get(fields[1]):
					email_id = d.get(fields[0])
					if validate_email_address(email_id):
						recipients.append(email_id)
			# field from parent doc
			else:
				email_ids_value = doc.get(fields[0])
				if validate_email_address(email_ids_value):
					email_ids = email_ids_value.replace(",", "\n")
					recipients = recipients + email_ids.split("\n")

		cc.extend(get_emails_from_template(recipient.cc, context))
		bcc.extend(get_emails_from_template(recipient.bcc, context))

		# For sending emails to specified role
		if recipient.receiver_by_role:
			emails = get_info_based_on_role(recipient.receiver_by_role, "email", ignore_permissions=True)

			for email in emails:
				recipients = recipients + email.split("\n")

	if self.send_to_all_assignees:
		recipients = recipients + get_assignees(doc)

	return list(set(recipients)), list(set(cc)), list(set(bcc))


class EmailNotificationHandlerAdapter(OutgoingCommunicationHandler, NotificationHandler):
	"""
	This is an adapter class that implements the outgoing communication and notification handler interfaces.

	It bridges the comms and email modules.
	"""

	_communication_medium = "Email"

	def _validate_communication(self, comm: Communication):
		attachments = []  # TODO
		comm.has_attachment = 1 if attachments else 0
		pass

	def _send_implementation(self, comm: Communication):
		attachments = []  # TODO
		if not comm.get_outgoing_email_account():
			frappe.throw(
				_(
					"Unable to send mail because of a missing email account. Please setup default Email Account from Settings > Email Account"
				),
				exc=frappe.OutgoingEmailError,
			)
		comm.send_email(
			print_html=None,
			print_format=None,
			send_me_a_copy=False,
			# TODO: implement attachments via communication
			print_letterhead=((attachments and attachments[0].get("print_letterhead")) or False),
		)

		return comm.recipients

	def _get_notification_recipients(
		self, notification: Notification, doc: Document, context: dict
	) -> tuple(list[str], list[str], list[str]):
		"""return receiver list based on the doc field and role specified"""
		recipients, cc, bcc = get_list_of_recipients(notification, doc, context)
		return recipients, cc, bcc

	def _get_notification_sender(
		self, notification: Notification, doc: Document, context: dict
	) -> str:
		from email.utils import formataddr

		sender = None
		if notification.sender and notification.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		return sender


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
	attachments=None,
	send_me_a_copy=False,
	cc=None,
	bcc=None,
	read_receipt=None,
	print_letterhead=True,
	email_template=None,
	communication_type=None,
	send_after=None,
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
	:param attachments: List of File names or dicts with keys "fname" and "fcontent"
	:param send_me_a_copy: Send a copy to the sender (default **False**).
	:param email_template: Template which is used to compose mail .
	:param send_after: Send after the given datetime.
	"""
	if kwargs:
		from frappe.utils.commands import warn

		warn(
			f"Options {kwargs} used in frappe.communications.email.make " "are deprecated or unsupported",
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
		send_after=send_after,
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
	attachments=None,
	send_me_a_copy=False,
	cc=None,
	bcc=None,
	read_receipt=None,
	print_letterhead=True,
	email_template=None,
	communication_type=None,
	add_signature=True,
	send_after=None,
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
			"send_after": send_after,
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
					"Unable to send mail because of a missing email account. Please setup default Email Account from Settings > Email Account"
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


@frappe.whitelist(allow_guest=True, methods=("GET",))
def mark_email_as_seen(name: str = None):
	frappe.request.after_response.add(lambda: _mark_email_as_seen(name))
	frappe.response.update(frappe.utils.get_imaginary_pixel_response())


def _mark_email_as_seen(name):
	try:
		update_communication_as_read(name)
	except Exception:
		frappe.log_error("Unable to mark as seen", None, "Communication", name)

	frappe.db.commit()  # nosemgrep: after_response requires explicit commit


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


class CommunicationEmailMixin:
	"""Mixin class to handle communication mails."""

	def is_email_communication(self):
		return self.communication_type == "Communication" and self.communication_medium == "Email"

	def get_owner(self):
		"""Get owner of the communication docs parent."""
		parent_doc = get_parent_doc(self)
		return parent_doc.owner if parent_doc else None

	def get_all_email_addresses(self, exclude_displayname=False):
		"""Get all Email addresses mentioned in the doc along with display name."""
		return (
			self.to_list(exclude_displayname=exclude_displayname)
			+ self.cc_list(exclude_displayname=exclude_displayname)
			+ self.bcc_list(exclude_displayname=exclude_displayname)
		)

	def get_email_with_displayname(self, email_address):
		"""Return email address after adding displayname."""
		display_name, email = parse_addr(email_address)
		if display_name and display_name != email:
			return email_address

		# emailid to emailid with display name map.
		email_map = {parse_addr(email)[1]: email for email in self.get_all_email_addresses()}
		return email_map.get(email, email)

	def mail_recipients(self, is_inbound_mail_communcation=False):
		"""Build to(recipient) list to send an email."""
		# Incase of inbound mail, recipients already received the mail, no need to send again.
		if is_inbound_mail_communcation:
			return []

		if hasattr(self, "_final_recipients"):
			return self._final_recipients

		to = self.to_list()
		self._final_recipients = list(filter(lambda id: id != "Administrator", to))
		return self._final_recipients

	def get_mail_recipients_with_displayname(self, is_inbound_mail_communcation=False):
		"""Build to(recipient) list to send an email including displayname in email."""
		to_list = self.mail_recipients(is_inbound_mail_communcation=is_inbound_mail_communcation)
		return [self.get_email_with_displayname(email) for email in to_list]

	def mail_cc(self, is_inbound_mail_communcation=False, include_sender=False):
		"""Build cc list to send an email.

		* if email copy is requested by sender, then add sender to CC.
		* If this doc is created through inbound mail, then add doc owner to cc list
		* remove all the thread_notify disabled users.
		* Remove standard users from email list
		"""
		if hasattr(self, "_final_cc"):
			return self._final_cc

		cc = self.cc_list()

		if include_sender:
			sender = self.sender_mailid
			# if user has selected send_me_a_copy, use their email as sender
			if frappe.session.user not in frappe.STANDARD_USERS:
				sender = frappe.db.get_value("User", frappe.session.user, "email")
			cc.append(sender)

		if is_inbound_mail_communcation:
			# inform parent document owner incase communication is created through inbound mail
			if doc_owner := self.get_owner():
				cc.append(doc_owner)
			cc = set(cc) - {self.sender_mailid}
			assignees = set(self.get_assignees())
			# Check and remove If user disabled notifications for incoming emails on assigned document.
			for assignee in assignees.copy():
				if not is_email_notifications_enabled_for_type(assignee, "threads_on_assigned_document"):
					assignees.remove(assignee)
			cc.update(assignees)

		cc = set(cc) - set(self.filter_thread_notification_disbled_users(cc))
		cc = cc - set(self.mail_recipients(is_inbound_mail_communcation=is_inbound_mail_communcation))

		# # Incase of inbound mail, to and cc already received the mail, no need to send again.
		if is_inbound_mail_communcation:
			cc = cc - set(self.cc_list() + self.to_list())

		self._final_cc = [m for m in cc if m and m not in frappe.STANDARD_USERS]
		return self._final_cc

	def get_mail_cc_with_displayname(self, is_inbound_mail_communcation=False, include_sender=False):
		cc_list = self.mail_cc(
			is_inbound_mail_communcation=is_inbound_mail_communcation, include_sender=include_sender
		)
		return [self.get_email_with_displayname(email) for email in cc_list if email]

	def mail_bcc(self, is_inbound_mail_communcation=False):
		"""
		* Thread_notify check
		* Email unsubscribe list
		* remove standard users.
		"""
		if hasattr(self, "_final_bcc"):
			return self._final_bcc

		bcc = set(self.bcc_list())
		if is_inbound_mail_communcation:
			bcc = bcc - {self.sender_mailid}
		bcc = bcc - set(self.filter_thread_notification_disbled_users(bcc))
		bcc = bcc - set(self.mail_recipients(is_inbound_mail_communcation=is_inbound_mail_communcation))

		# Incase of inbound mail, to and cc & bcc already received the mail, no need to send again.
		if is_inbound_mail_communcation:
			bcc = bcc - set(self.bcc_list() + self.to_list())

		self._final_bcc = [m for m in bcc if m not in frappe.STANDARD_USERS]
		return self._final_bcc

	def get_mail_bcc_with_displayname(self, is_inbound_mail_communcation=False):
		bcc_list = self.mail_bcc(is_inbound_mail_communcation=is_inbound_mail_communcation)
		return [self.get_email_with_displayname(email) for email in bcc_list if email]

	def mail_sender(self):
		email_account = self.get_outgoing_email_account()
		if not self.sender_mailid and email_account:
			return email_account.email_id
		return self.sender_mailid

	def mail_sender_fullname(self):
		email_account = self.get_outgoing_email_account()
		if not self.sender_full_name:
			return (email_account and email_account.name) or _("Notification")
		return self.sender_full_name

	def get_mail_sender_with_displayname(self):
		return get_formatted_email(self.mail_sender_fullname(), mail=self.mail_sender())

	def get_content(self, print_format=None):
		if print_format and frappe.db.get_single_value("System Settings", "attach_view_link"):
			return self.content + self.get_attach_link(print_format)
		return self.content

	def get_attach_link(self, print_format):
		"""Return public link for the attachment via `templates/emails/print_link.html`."""
		return frappe.get_template("templates/emails/print_link.html").render(
			{
				"url": get_url(),
				"doctype": self.reference_doctype,
				"name": self.reference_name,
				"print_format": print_format,
				"key": get_parent_doc(self).get_document_share_key(),
			}
		)

	def get_outgoing_email_account(self):
		if not hasattr(self, "_outgoing_email_account"):
			if self.email_account:
				self._outgoing_email_account = EmailAccount.find(self.email_account)
			else:
				self._outgoing_email_account = EmailAccount.find_outgoing(
					match_by_email=self.sender_mailid, match_by_doctype=self.reference_doctype
				)

				if self.sent_or_received == "Sent" and self._outgoing_email_account:
					if frappe.db.exists("Email Account", self._outgoing_email_account.name):
						self.db_set("email_account", self._outgoing_email_account.name)

		return self._outgoing_email_account

	def get_incoming_email_account(self):
		if not hasattr(self, "_incoming_email_account"):
			self._incoming_email_account = EmailAccount.find_incoming(
				match_by_email=self.sender_mailid, match_by_doctype=self.reference_doctype
			)
		return self._incoming_email_account

	def mail_attachments(self, print_format=None, print_html=None):
		final_attachments = []

		if print_format or print_html:
			d = {
				"print_format": print_format,
				"html": print_html,
				"print_format_attachment": 1,
				"doctype": self.reference_doctype,
				"name": self.reference_name,
			}
			final_attachments.append(d)

		final_attachments.extend({"fid": a["name"]} for a in self.get_attachments() or [])
		return final_attachments

	def get_unsubscribe_message(self):
		email_account = self.get_outgoing_email_account()
		if email_account and email_account.send_unsubscribe_message:
			return _("Leave this conversation")
		return ""

	def exclude_emails_list(self, is_inbound_mail_communcation=False, include_sender=False) -> list:
		"""List of mail id's excluded while sending mail."""
		all_ids = self.get_all_email_addresses(exclude_displayname=True)

		final_ids = (
			self.mail_recipients(is_inbound_mail_communcation=is_inbound_mail_communcation)
			+ self.mail_bcc(is_inbound_mail_communcation=is_inbound_mail_communcation)
			+ self.mail_cc(
				is_inbound_mail_communcation=is_inbound_mail_communcation, include_sender=include_sender
			)
		)

		return list(set(all_ids) - set(final_ids))

	def get_assignees(self):
		"""Get owners of the reference document."""
		filters = {
			"status": "Open",
			"reference_name": self.reference_name,
			"reference_type": self.reference_doctype,
		}

		if self.reference_doctype and self.reference_name:
			return ToDo.get_owners(filters)
		else:
			return []

	@staticmethod
	def filter_thread_notification_disbled_users(emails):
		"""Filter users based on notifications for email threads setting is disabled."""
		if not emails:
			return []

		return frappe.get_all(
			"User", pluck="email", filters={"email": ["in", emails], "thread_notify": 0}
		)

	@staticmethod
	def filter_disabled_users(emails):
		""" """
		if not emails:
			return []

		return frappe.get_all("User", pluck="email", filters={"email": ["in", emails], "enabled": 0})

	def sendmail_input_dict(
		self,
		print_html=None,
		print_format=None,
		send_me_a_copy=None,
		print_letterhead=None,
		is_inbound_mail_communcation=None,
	) -> dict:

		outgoing_email_account = self.get_outgoing_email_account()
		if not outgoing_email_account:
			return {}

		recipients = self.get_mail_recipients_with_displayname(
			is_inbound_mail_communcation=is_inbound_mail_communcation
		)
		cc = self.get_mail_cc_with_displayname(
			is_inbound_mail_communcation=is_inbound_mail_communcation, include_sender=send_me_a_copy
		)
		bcc = self.get_mail_bcc_with_displayname(
			is_inbound_mail_communcation=is_inbound_mail_communcation
		)

		if not (recipients or cc):
			return {}

		final_attachments = self.mail_attachments(print_format=print_format, print_html=print_html)
		incoming_email_account = self.get_incoming_email_account()
		return {
			"recipients": recipients,
			"cc": cc,
			"bcc": bcc,
			"expose_recipients": "header",
			"sender": self.get_mail_sender_with_displayname(),
			"reply_to": incoming_email_account and incoming_email_account.email_id,
			"subject": self.subject,
			"content": self.get_content(print_format=print_format),
			"reference_doctype": self.reference_doctype,
			"reference_name": self.reference_name,
			"attachments": final_attachments,
			"message_id": self.message_id,
			"unsubscribe_message": self.get_unsubscribe_message(),
			"delayed": True,
			"communication": self.name,
			"read_receipt": self.read_receipt,
			"is_notification": (self.sent_or_received == "Received"),
			"print_letterhead": print_letterhead,
			"send_after": self.send_after,
		}

	def send_email(
		self,
		print_html=None,
		print_format=None,
		send_me_a_copy=None,
		print_letterhead=None,
		is_inbound_mail_communcation=None,
	):
		if input_dict := self.sendmail_input_dict(
			print_html=print_html,
			print_format=print_format,
			send_me_a_copy=send_me_a_copy,
			print_letterhead=print_letterhead,
			is_inbound_mail_communcation=is_inbound_mail_communcation,
		):
			frappe.sendmail(**input_dict)
