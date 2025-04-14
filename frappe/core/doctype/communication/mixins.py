import frappe
from frappe import _
from frappe.core.utils import get_parent_doc
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled_for_type,
)
from frappe.desk.doctype.todo.todo import ToDo
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.utils import cstr, get_formatted_email, get_url, parse_addr


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
			assignees = set(self.get_assignees()) - {self.sender_mailid}
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
		if print_format and frappe.get_system_settings("attach_view_link"):
			return cstr(self.content) + self.get_attach_link(print_format)
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

	def mail_attachments(self, print_format=None, print_html=None, print_language=None):
		final_attachments = []

		if print_format or print_html:
			d = {
				"print_format": print_format,
				"html": print_html,
				"print_format_attachment": 1,
				"doctype": self.reference_doctype,
				"name": self.reference_name,
				"lang": print_language or frappe.local.lang,
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

		return frappe.get_all("User", pluck="email", filters={"email": ["in", emails], "thread_notify": 0})

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
		print_language=None,
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
		bcc = self.get_mail_bcc_with_displayname(is_inbound_mail_communcation=is_inbound_mail_communcation)

		if not (recipients or cc):
			return {}

		final_attachments = self.mail_attachments(
			print_format=print_format, print_html=print_html, print_language=print_language
		)
		incoming_email_account = self.get_incoming_email_account()

		reply_to = None

		# If this is a reply to an existing email, set reply_to as the sender of the reply
		if self.in_reply_to:
			reply_to = self.get_mail_sender_with_displayname()
		elif incoming_email_account:
			reply_to = incoming_email_account.email_id

		return {
			"recipients": recipients,
			"cc": cc,
			"bcc": bcc,
			"expose_recipients": "header",
			"sender": self.get_mail_sender_with_displayname(),
			"reply_to": reply_to,
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
		print_language=None,
		now=False,
	):
		if input_dict := self.sendmail_input_dict(
			print_html=print_html,
			print_format=print_format,
			send_me_a_copy=send_me_a_copy,
			print_letterhead=print_letterhead,
			is_inbound_mail_communcation=is_inbound_mail_communcation,
			print_language=print_language,
		):
			frappe.sendmail(now=now, **input_dict)
