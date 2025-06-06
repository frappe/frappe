# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
import quopri
import traceback
from contextlib import suppress
from email.parser import Parser
from email.policy import SMTP
from typing import TYPE_CHECKING

import frappe
from frappe import _, safe_encode, task
from frappe.core.utils import html2text
from frappe.database.database import savepoint
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.email_body import add_attachment, get_email, get_formatted_html
from frappe.email.frappemail import FrappeMail
from frappe.email.queue import get_unsubcribed_url, get_unsubscribe_message
from frappe.email.smtp import SMTPServer
from frappe.model.document import Document
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now
from frappe.utils import (
	add_days,
	cint,
	cstr,
	get_hook_method,
	get_string_between,
	get_url,
	now,
	nowdate,
	sbool,
	split_emails,
)
from frappe.utils.verified_command import get_signed_params

if TYPE_CHECKING:
	from typing import Literal


class EmailQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.email.doctype.email_queue_recipient.email_queue_recipient import EmailQueueRecipient
		from frappe.types import DF

		add_unsubscribe_link: DF.Check
		attachments: DF.Code | None
		communication: DF.Link | None
		email_account: DF.Link | None
		error: DF.Code | None
		expose_recipients: DF.Data | None
		message: DF.Code | None
		message_id: DF.SmallText | None
		priority: DF.Int
		recipients: DF.Table[EmailQueueRecipient]
		reference_doctype: DF.Link | None
		reference_name: DF.Data | None
		retry: DF.Int
		send_after: DF.Datetime | None
		sender: DF.Data | None
		show_as_cc: DF.SmallText | None
		status: DF.Literal["Not Sent", "Sending", "Sent", "Partially Sent", "Error"]
		unsubscribe_method: DF.Data | None
		unsubscribe_params: DF.Code | None
	# end: auto-generated types

	DOCTYPE = "Email Queue"

	def set_recipients(self, recipients):
		self.set("recipients", [])
		for r in recipients:
			self.append("recipients", {"recipient": r.strip(), "status": "Not Sent"})

	def on_trash(self):
		self.prevent_email_queue_delete()

	def prevent_email_queue_delete(self):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Email Queue"))

	def get_duplicate(self, recipients):
		values = self.as_dict()
		del values["name"]
		duplicate = frappe.get_doc(values)
		duplicate.set_recipients(recipients)
		return duplicate

	@classmethod
	def new(cls, doc_data, ignore_permissions=False) -> EmailQueue:
		data = doc_data.copy()
		if not data.get("recipients"):
			return

		if isinstance(data["unsubscribe_params"], dict):
			data["unsubscribe_params"] = json.dumps(data["unsubscribe_params"])

		recipients = data.pop("recipients")
		doc = frappe.new_doc(cls.DOCTYPE)
		doc.update(data)
		doc.set_recipients(recipients)
		doc.insert(ignore_permissions=ignore_permissions)
		return doc

	@classmethod
	def find(cls, name) -> EmailQueue:
		return frappe.get_doc(cls.DOCTYPE, name)

	@classmethod
	def find_one_by_filters(cls, **kwargs):
		name = frappe.db.get_value(cls.DOCTYPE, kwargs)
		return cls.find(name) if name else None

	def update_db(self, commit=False, **kwargs):
		frappe.db.set_value(self.DOCTYPE, self.name, kwargs)
		if commit:
			frappe.db.commit()

	def update_status(self, status, commit=False, **kwargs):
		self.update_db(status=status, commit=commit, **kwargs)
		if self.communication:
			communication_doc = frappe.get_doc("Communication", self.communication)
			communication_doc.set_delivery_status(commit=commit)

	@property
	def cc(self):
		return (self.show_as_cc and self.show_as_cc.split(",")) or []

	@property
	def to(self):
		return [r.recipient for r in self.recipients if r.recipient not in self.cc]

	@property
	def attachments_list(self):
		return json.loads(self.attachments) if self.attachments else []

	def get_email_account(self, raise_error=False):
		if self.email_account:
			return frappe.get_cached_doc("Email Account", self.email_account)

		return EmailAccount.find_outgoing(
			match_by_email=self.sender, match_by_doctype=self.reference_doctype, _raise_error=raise_error
		)

	def is_to_be_sent(self):
		return self.status in ["Not Sent", "Partially Sent"]

	def can_send_now(self):
		if (
			frappe.are_emails_muted()
			or not self.is_to_be_sent()
			or cint(frappe.db.get_default("suspend_email_queue")) == 1
		):
			return False

		return True

	def send(
		self,
		smtp_server_instance: SMTPServer = None,
		frappe_mail_client: FrappeMail = None,
		force_send: bool = False,
	):
		"""Send emails to recipients."""
		if not self.can_send_now() and not force_send:
			return

		with SendMailContext(self, smtp_server_instance, frappe_mail_client) as ctx:
			ctx.fetch_outgoing_server()
			message = None
			for recipient in self.recipients:
				if recipient.is_mail_sent():
					continue

				message = ctx.build_message(recipient.recipient)
				if method := get_hook_method("override_email_send"):
					method(self, self.sender, recipient.recipient, message)
				elif not frappe.flags.in_test or frappe.flags.testing_email:
					if ctx.email_account_doc.service == "Frappe Mail":
						is_newsletter = self.reference_doctype == "Newsletter"
						ctx.frappe_mail_client.send_raw(
							sender=self.sender,
							recipients=recipient.recipient,
							message=message,
							is_newsletter=is_newsletter,
						)
					else:
						ctx.smtp_server.session.sendmail(
							from_addr=self.sender,
							to_addrs=recipient.recipient,
							msg=message.decode("utf-8").encode(),
						)

				ctx.update_recipient_status_to_sent(recipient)

			if frappe.flags.in_test and not frappe.flags.testing_email:
				frappe.flags.sent_mail = message
				return

			if ctx.email_account_doc.append_emails_to_sent_folder:
				ctx.email_account_doc.append_email_to_sent_folder(message)

	@staticmethod
	def clear_old_logs(days=30):
		"""Remove low priority older than 31 days in Outbox or configured in Log Settings.
		Note: Used separate query to avoid deadlock
		"""
		days = days or 31
		email_queue = frappe.qb.DocType("Email Queue")
		email_recipient = frappe.qb.DocType("Email Queue Recipient")

		# Delete queue table
		(
			frappe.qb.from_(email_queue).delete().where(email_queue.creation < (Now() - Interval(days=days)))
		).run()

		# delete child tables, note that this has potential to leave some orphan
		# child table behind if modified time was later than parent doc (rare).
		# But it's safe since child table doesn't contain links.
		(
			frappe.qb.from_(email_recipient)
			.delete()
			.where(email_recipient.creation < (Now() - Interval(days=days)))
		).run()


from frappe.deprecation_dumpster import send_mail as _send_mail

send_mail = task(queue="short")(_send_mail)


class SendMailContext:
	def __init__(
		self,
		queue_doc: Document,
		smtp_server_instance: SMTPServer = None,
		frappe_mail_client: FrappeMail = None,
	):
		self.queue_doc: EmailQueue = queue_doc
		self.smtp_server: SMTPServer = smtp_server_instance
		self.frappe_mail_client: FrappeMail = frappe_mail_client
		self.sent_to_atleast_one_recipient = any(
			rec.recipient for rec in self.queue_doc.recipients if rec.is_mail_sent()
		)
		self.email_account_doc = None

	def fetch_outgoing_server(self):
		self.email_account_doc = self.queue_doc.get_email_account(raise_error=True)

		if self.email_account_doc.service == "Frappe Mail":
			if not self.frappe_mail_client:
				self.frappe_mail_client = self.email_account_doc.get_frappe_mail_client()
		elif not self.smtp_server:
			self.smtp_server = self.email_account_doc.get_smtp_server()

	def __enter__(self):
		self.queue_doc.update_status(status="Sending", commit=True)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type:
			update_fields = {"error": frappe.get_traceback()}
			if self.queue_doc.retry < get_email_retry_limit():
				update_fields.update(
					{
						"status": "Partially Sent" if self.sent_to_atleast_one_recipient else "Not Sent",
						"retry": self.queue_doc.retry + 1,
					}
				)
			else:
				update_fields.update({"status": "Error"})
				self.notify_failed_email()
		else:
			update_fields = {"status": "Sent"}

		self.queue_doc.update_status(**update_fields, commit=True)

	@savepoint(catch=Exception)
	def notify_failed_email(self):
		# Parse the email body to extract the subject
		subject = Parser(policy=SMTP).parsestr(self.queue_doc.message)["Subject"]

		# Construct the notification
		notification = frappe.new_doc("Notification Log")
		notification.for_user = self.queue_doc.owner
		notification.set("type", "Alert")
		notification.from_user = self.queue_doc.owner
		notification.document_type = self.queue_doc.doctype
		notification.document_name = self.queue_doc.name
		notification.subject = _("Failed to send email with subject:") + f" {subject}"
		notification.insert()

	def update_recipient_status_to_sent(self, recipient):
		self.sent_to_atleast_one_recipient = True
		recipient.update_db(status="Sent", commit=True)

	def get_message_object(self, message):
		return Parser(policy=SMTP).parsestr(message)

	def message_placeholder(self, placeholder_key):
		# sourcery skip: avoid-builtin-shadow
		map = {
			"tracker": "<!--email_open_check-->",
			"unsubscribe_url": "<!--unsubscribe_url-->",
			"cc": "<!--cc_message-->",
			"recipient": "<!--recipient-->",
		}
		return map.get(placeholder_key)

	def build_message(self, recipient_email) -> bytes:
		"""Build message specific to the recipient."""
		message = self.queue_doc.message

		if not message:
			return ""

		message = message.replace(self.message_placeholder("tracker"), self.get_tracker_str(recipient_email))
		message = message.replace(
			self.message_placeholder("unsubscribe_url"), self.get_unsubscribe_str(recipient_email)
		)
		message = message.replace(self.message_placeholder("cc"), self.get_receivers_str())
		message = message.replace(
			self.message_placeholder("recipient"), self.get_recipient_str(recipient_email)
		)
		message = self.include_attachments(message)
		return message

	def get_tracker_str(self, recipient_email) -> str:
		tracker_url = ""
		if self.queue_doc.get("email_read_tracker_url"):
			email_read_tracker_url = self.queue_doc.email_read_tracker_url
			params = {
				"recipient_email": recipient_email,
				"reference_name": self.queue_doc.reference_name,
				"reference_doctype": self.queue_doc.reference_doctype,
			}
			tracker_url = get_url(f"{email_read_tracker_url}?{get_signed_params(params)}")

		elif (
			self.email_account_doc
			and self.email_account_doc.track_email_status
			and self.queue_doc.communication
		):
			tracker_url = f"{get_url()}/api/method/frappe.core.doctype.communication.email.mark_email_as_seen?name={self.queue_doc.communication}"

		if tracker_url:
			tracker_url_html = f'<img src="{tracker_url}"/>'
			return quopri.encodestring(tracker_url_html.encode()).decode()

		return ""

	def get_unsubscribe_str(self, recipient_email: str) -> str:
		unsubscribe_url = ""

		if self.queue_doc.add_unsubscribe_link and self.queue_doc.reference_doctype:
			unsubscribe_url = get_unsubcribed_url(
				reference_doctype=self.queue_doc.reference_doctype,
				reference_name=self.queue_doc.reference_name,
				email=recipient_email,
				unsubscribe_method=self.queue_doc.unsubscribe_method,
				unsubscribe_params=self.queue_doc.unsubscribe_params,
			)

		return quopri.encodestring(unsubscribe_url.encode()).decode()

	def get_receivers_str(self):
		message = ""
		if self.queue_doc.expose_recipients == "footer":
			to_str = ", ".join(self.queue_doc.to)
			cc_str = ", ".join(self.queue_doc.cc)
			message = f"This email was sent to {to_str}"
			message = f"{message} and copied to {cc_str}" if cc_str else message
		return message

	def get_recipient_str(self, recipient_email):
		return recipient_email if self.queue_doc.expose_recipients != "header" else ""

	def include_attachments(self, message):
		message_obj = self.get_message_object(message)
		attachments = self.queue_doc.attachments_list

		for attachment in attachments:
			if attachment.get("fcontent"):
				continue

			file_filters = {}
			if attachment.get("fid"):
				file_filters["name"] = attachment.get("fid")
			elif attachment.get("file_url"):
				file_filters["file_url"] = attachment.get("file_url")

			if file_filters:
				_file = frappe.get_doc("File", file_filters)
				fcontent = _file.get_content()
				attachment.update({"fname": _file.file_name, "fcontent": fcontent, "parent": message_obj})
				attachment.pop("fid", None)
				attachment.pop("file_url", None)
				add_attachment(**attachment)

			elif attachment.get("print_format_attachment") == 1:
				attachment.pop("print_format_attachment", None)
				print_format_file = frappe.attach_print(**attachment)
				self._store_file(print_format_file["fname"], print_format_file["fcontent"])
				print_format_file.update({"parent": message_obj})
				add_attachment(**print_format_file)

		return safe_encode(message_obj.as_string())

	def _store_file(self, file_name, content):
		if not frappe.get_system_settings("store_attached_pdf_document"):
			return

		file_data = frappe._dict(file_name=file_name, is_private=1)

		# Store on communication if available, else email queue doc
		if self.queue_doc.communication:
			file_data.attached_to_doctype = "Communication"
			file_data.attached_to_name = self.queue_doc.communication
		else:
			file_data.attached_to_doctype = self.queue_doc.doctype
			file_data.attached_to_name = self.queue_doc.name

		if frappe.db.exists("File", file_data):
			return

		file = frappe.new_doc("File", **file_data)
		file.content = content
		file.insert()


@frappe.whitelist()
def retry_sending(queues: str | list[str]):
	if not frappe.has_permission("Email Queue", throw=True):
		return

	if isinstance(queues, str):
		queues = json.loads(queues)

	if not queues:
		return

	# NOTE: this will probably work fine with the way current listview works (showing and selecting 20-20 records)
	# but, ideally this should be enqueued
	email_queue = frappe.qb.DocType("Email Queue")
	frappe.qb.update(email_queue).set(email_queue.status, "Not Sent").set(email_queue.modified, now()).set(
		email_queue.modified_by, frappe.session.user
	).where(email_queue.name.isin(queues) & email_queue.status == "Error").run()


@frappe.whitelist()
def send_now(name, force_send: bool = False):
	record = EmailQueue.find(name)
	if record:
		record.check_permission()
		record.send(force_send=force_send)


@frappe.whitelist()
def toggle_sending(enable):
	frappe.only_for("System Manager")
	frappe.db.set_default("suspend_email_queue", 0 if sbool(enable) else 1)


def on_doctype_update():
	"""Add index in `tabCommunication` for `(reference_doctype, reference_name)`"""
	frappe.db.add_index("Email Queue", ("status", "send_after", "priority", "creation"), "index_bulk_flush")

	frappe.db.add_index("Email Queue", ["message_id(140)"])


def get_email_retry_limit():
	return cint(frappe.db.get_system_setting("email_retry_limit")) or 3


class QueueBuilder:
	"""Builds Email Queue from the given data"""

	def __init__(
		self,
		recipients=None,
		sender=None,
		subject=None,
		message=None,
		text_content=None,
		reference_doctype=None,
		reference_name=None,
		unsubscribe_method=None,
		unsubscribe_params=None,
		unsubscribe_message=None,
		attachments=None,
		reply_to=None,
		cc=None,
		bcc=None,
		message_id=None,
		in_reply_to=None,
		send_after=None,
		expose_recipients=None,
		send_priority=1,
		communication=None,
		read_receipt=None,
		queue_separately=False,
		is_notification=False,
		add_unsubscribe_link=1,
		inline_images=None,
		header=None,
		print_letterhead=False,
		with_container=False,
		email_read_tracker_url=None,
		x_priority: Literal[1, 3, 5] = 3,
		email_headers=None,
	):
		"""Add email to sending queue (Email Queue)

		:param recipients: List of recipients.
		:param sender: Email sender.
		:param subject: Email subject.
		:param message: Email message.
		:param text_content: Text version of email message.
		:param reference_doctype: Reference DocType of caller document.
		:param reference_name: Reference name of caller document.
		:param send_priority: Priority for Email Queue, default 1.
		:param unsubscribe_method: URL method for unsubscribe. Default is `/api/method/frappe.email.queue.unsubscribe`.
		:param unsubscribe_params: additional params for unsubscribed links. default are name, doctype, email
		:param attachments: Attachments to be sent.
		:param reply_to: Reply to be captured here (default inbox)
		:param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
		:param send_after: Send this email after the given datetime. If value is in integer, then `send_after` will be the automatically set to no of days from current date.
		:param communication: Communication link to be set in Email Queue record
		:param queue_separately: Queue each email separately
		:param is_notification: Marks email as notification so will not trigger notifications from system
		:param add_unsubscribe_link: Send unsubscribe link in the footer of the Email, default 1.
		:param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
		:param header: Append header in email (boolean)
		:param with_container: Wraps email inside styled container
		:param email_read_tracker_url: A URL for tracking whether an email is read by the recipient.
		:param x_priority: 1 = HIGHEST, 3 = NORMAL, 5 = LOWEST
		:param email_headers: Additional headers to be added in the email, e.g. {"X-Custom-Header": "value"} or {"Custom-Header": "value"}. Automatically prepends "X-" to the header name if not present.
		"""

		self._unsubscribe_method = unsubscribe_method
		self._recipients = recipients
		self._cc = cc
		self._bcc = bcc
		self._send_after = send_after
		self._sender = sender
		self._text_content = text_content
		self._message = message
		self._x_priority: Literal[1, 3, 5] = x_priority
		self._add_unsubscribe_link = add_unsubscribe_link
		self._unsubscribe_message = unsubscribe_message
		self._attachments = attachments

		self._unsubscribed_user_emails = None
		self._email_account = None

		self.unsubscribe_params = unsubscribe_params
		self.subject = subject
		self.reference_doctype = reference_doctype
		self.reference_name = reference_name
		self.expose_recipients = expose_recipients
		self.with_container = with_container
		self.header = header
		self.reply_to = reply_to
		self.message_id = message_id
		self.in_reply_to = in_reply_to
		self.send_priority = send_priority
		self.communication = communication
		self.read_receipt = read_receipt
		self.queue_separately = queue_separately
		self.is_notification = is_notification
		self.inline_images = inline_images
		self.print_letterhead = print_letterhead
		self.email_read_tracker_url = email_read_tracker_url
		self.email_headers = email_headers

	@property
	def unsubscribe_method(self):
		return self._unsubscribe_method or "/api/method/frappe.email.queue.unsubscribe"

	def _get_emails_list(self, emails=None):
		emails = split_emails(emails) if isinstance(emails, str) else (emails or [])
		return [each for each in set(emails) if each]

	@property
	def recipients(self):
		return self._get_emails_list(self._recipients)

	@property
	def cc(self):
		return self._get_emails_list(self._cc)

	@property
	def bcc(self):
		return self._get_emails_list(self._bcc)

	@property
	def send_after(self):
		if isinstance(self._send_after, int):
			return add_days(nowdate(), self._send_after)
		return self._send_after

	@property
	def sender(self):
		if not self._sender or self._sender == "Administrator":
			email_account = self.get_outgoing_email_account()
			return email_account.default_sender
		return self._sender

	def email_text_content(self):
		unsubscribe_msg = self.unsubscribe_message()
		unsubscribe_text_message = (unsubscribe_msg and unsubscribe_msg.text) or ""

		if self._text_content:
			return self._text_content + unsubscribe_text_message

		try:
			text_content = html2text(self._message)
		except Exception:
			text_content = "See html attachment"
		return text_content + unsubscribe_text_message

	def email_html_content(self):
		email_account = self.get_outgoing_email_account()
		return get_formatted_html(
			self.subject,
			self._message,
			header=self.header,
			email_account=email_account,
			unsubscribe_link=self.unsubscribe_message(),
			with_container=self.with_container,
		)

	def should_include_unsubscribe_link(self):
		return (
			self._add_unsubscribe_link == 1
			and self.reference_doctype
			and (self._unsubscribe_message or self.reference_doctype == "Newsletter")
		)

	def unsubscribe_message(self):
		if self.should_include_unsubscribe_link():
			return get_unsubscribe_message(self._unsubscribe_message, self.expose_recipients)

	def get_outgoing_email_account(self):
		if self._email_account:
			return self._email_account

		self._email_account = EmailAccount.find_outgoing(
			match_by_doctype=self.reference_doctype, match_by_email=self._sender, _raise_error=True
		)
		return self._email_account

	def get_unsubscribed_user_emails(self):
		if self._unsubscribed_user_emails is not None:
			return self._unsubscribed_user_emails

		all_ids = list(set(self.recipients + self.cc))

		EmailUnsubscribe = DocType("Email Unsubscribe")

		if len(all_ids) > 0:
			unsubscribed = (
				frappe.qb.from_(EmailUnsubscribe)
				.select(EmailUnsubscribe.email)
				.where(
					EmailUnsubscribe.email.isin(all_ids)
					& (
						(
							(EmailUnsubscribe.reference_doctype == self.reference_doctype)
							& (EmailUnsubscribe.reference_name == self.reference_name)
						)
						| (EmailUnsubscribe.global_unsubscribe == 1)
					)
				)
				.distinct()
			).run(pluck=True)
		else:
			unsubscribed = None

		self._unsubscribed_user_emails = unsubscribed or []
		return self._unsubscribed_user_emails

	def final_recipients(self):
		unsubscribed_emails = self.get_unsubscribed_user_emails()
		return [mail_id for mail_id in self.recipients if mail_id not in unsubscribed_emails]

	def final_cc(self):
		unsubscribed_emails = self.get_unsubscribed_user_emails()
		return [mail_id for mail_id in self.cc if mail_id not in unsubscribed_emails]

	def get_attachments(self):
		attachments = []
		if self._attachments:
			# store attachments with fid or print format details, to be attached on-demand later
			for att in self._attachments:
				if att.get("fid") or att.get("file_url"):
					attachments.append(att)
				elif att.get("print_format_attachment") == 1:
					if not att.get("lang", None):
						att["lang"] = frappe.local.lang
					att["print_letterhead"] = self.print_letterhead
					attachments.append(att)
		return attachments

	def prepare_email_content(self):
		email_account = self.get_outgoing_email_account()
		if email_account.always_bcc:
			self._bcc = [*self.bcc, email_account.always_bcc]
		mail = get_email(
			recipients=self.final_recipients(),
			sender=self.sender,
			subject=self.subject,
			formatted=self.email_html_content(),
			text_content=self.email_text_content(),
			attachments=self._attachments,
			reply_to=self.reply_to,
			cc=self.final_cc(),
			bcc=self.bcc,
			email_account=email_account,
			expose_recipients=self.expose_recipients,
			inline_images=self.inline_images,
			header=self.header,
			x_priority=self._x_priority,
		)

		mail.set_message_id(self.message_id, self.is_notification)

		if self.email_headers:
			mail.add_headers(self.email_headers)

		if self.read_receipt:
			mail.msg_root["Disposition-Notification-To"] = self.sender
		if self.in_reply_to:
			if message_id := frappe.db.get_value("Communication", self.in_reply_to, "message_id"):
				mail.set_in_reply_to(get_string_between("<", message_id, ">"))
		return mail

	def process(self, send_now=False) -> EmailQueue | None:
		"""Build and return the email queues those are created.

		Sends email incase if it is requested to send now.
		"""
		final_recipients = self.final_recipients()
		queue_separately = (final_recipients and self.queue_separately) or len(final_recipients) > 100
		if not (final_recipients + self.final_cc()):
			return []

		queue_data = self.as_dict(include_recipients=False)
		if not queue_data:
			return []

		if not queue_separately:
			recipients = list(set(final_recipients + self.final_cc() + self.bcc))
			q = EmailQueue.new({**queue_data, **{"recipients": recipients}}, ignore_permissions=True)
			send_now and q.send()
			return q
		else:
			if send_now and len(final_recipients) >= 1000:
				# force queueing if there are too many recipients to avoid timeouts
				send_now = False
			for recipients in frappe.utils.create_batch(final_recipients, 1000):
				frappe.enqueue(
					self.send_emails,
					queue_data=queue_data,
					final_recipients=recipients,
					job_name=frappe.utils.get_job_name(
						"send_bulk_emails_for", self.reference_doctype, self.reference_name
					),
					now=frappe.flags.in_test or send_now,
					queue="long",
				)

	def send_emails(self, queue_data, final_recipients):
		# This is used to bulk send emails from same sender to multiple recipients separately
		# This re-uses smtp server instance to minimize the cost of new session creation
		frappe_mail_client = None
		smtp_server_instance = None
		for r in final_recipients:
			recipients = list(set([r, *self.final_cc(), *self.bcc]))
			q = EmailQueue.new({**queue_data, **{"recipients": recipients}}, ignore_permissions=True)
			if not frappe_mail_client and not smtp_server_instance:
				email_account = q.get_email_account(raise_error=True)

				if email_account.service == "Frappe Mail":
					frappe_mail_client = email_account.get_frappe_mail_client()
				else:
					smtp_server_instance = email_account.get_smtp_server()

			with suppress(Exception):
				q.send(smtp_server_instance=smtp_server_instance, frappe_mail_client=frappe_mail_client)

		if smtp_server_instance:
			smtp_server_instance.quit()

	def as_dict(self, include_recipients=True):
		email_account = self.get_outgoing_email_account()
		email_account_name = email_account and email_account.is_exists_in_db() and email_account.name

		mail = self.prepare_email_content()
		try:
			mail_to_string = cstr(mail.as_string())
		except frappe.InvalidEmailAddressError:
			# bad Email Address - don't add to queue
			frappe.log_error(
				title="Invalid email address",
				message="Invalid email address Sender: {}, Recipients: {}, \nTraceback: {} ".format(
					self.sender, ", ".join(self.final_recipients()), traceback.format_exc()
				),
				reference_doctype=self.reference_doctype,
				reference_name=self.reference_name,
			)
			return

		d = {
			"priority": self.send_priority,
			"attachments": json.dumps(self.get_attachments()),
			"message_id": get_string_between("<", mail.msg_root["Message-Id"], ">"),
			"message": mail_to_string,
			"sender": mail.sender,
			"reference_doctype": self.reference_doctype,
			"reference_name": self.reference_name,
			"add_unsubscribe_link": self._add_unsubscribe_link,
			"unsubscribe_method": self.unsubscribe_method,
			"unsubscribe_params": self.unsubscribe_params,
			"expose_recipients": self.expose_recipients,
			"communication": self.communication,
			"send_after": self.send_after,
			"show_as_cc": ",".join(self.final_cc()),
			"show_as_bcc": ",".join(self.bcc),
			"email_account": email_account_name or None,
			"email_read_tracker_url": self.email_read_tracker_url,
		}

		if include_recipients:
			d["recipients"] = self.final_recipients()

		return d
