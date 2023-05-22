# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import smtplib
from functools import wraps

import frappe
from frappe import _
from frappe.email.receive import Timed_IMAP4, Timed_IMAP4_SSL, Timed_POP3, Timed_POP3_SSL
from frappe.email.utils import get_port
from frappe.model.document import Document
from frappe.utils import cint

EMAIL_DOMAIN_FIELDS = [
	"email_server",
	"use_imap",
	"use_ssl",
	"use_starttls",
	"use_tls",
	"attachment_limit",
	"smtp_server",
	"smtp_port",
	"use_ssl_for_outgoing",
	"append_emails_to_sent_folder",
	"incoming_port",
]


def get_error_message(event):
	return {
		"incoming": (_("Incoming email account not correct"), _("Error connecting via IMAP/POP3: {e}")),
		"outgoing": (_("Outgoing email account not correct"), _("Error connecting via SMTP: {e}")),
	}[event]


def handle_error(event):
	def decorator(fn):
		@wraps(fn)
		def wrapper(*args, **kwargs):
			err_title, err_message = get_error_message(event)
			try:
				fn(*args, **kwargs)
			except Exception as e:
				frappe.throw(
					title=err_title,
					msg=err_message.format(e=e),
				)

		return wrapper

	return decorator


class EmailDomain(Document):
	def validate(self):
		"""Validate POP3/IMAP and SMTP connections."""

		if frappe.local.flags.in_patch or frappe.local.flags.in_test or frappe.local.flags.in_install:
			return

		self.validate_incoming_server_conn()
		self.validate_outgoing_server_conn()

	def on_update(self):
		"""update all email accounts using this domain"""
		for email_account in frappe.get_all("Email Account", filters={"domain": self.name}):
			try:
				email_account = frappe.get_doc("Email Account", email_account.name)
				for attr in EMAIL_DOMAIN_FIELDS:
					email_account.set(attr, self.get(attr, default=0))
				email_account.save()

			except Exception as e:
				frappe.msgprint(
					_("Error has occurred in {0}").format(email_account.name), raise_exception=e.__class__
				)

	@handle_error("incoming")
	def validate_incoming_server_conn(self):
		self.incoming_port = get_port(self)

		if self.use_imap:
			conn_method = Timed_IMAP4_SSL if self.use_ssl else Timed_IMAP4
		else:
			conn_method = Timed_POP3_SSL if self.use_ssl else Timed_POP3

		self.use_starttls = cint(self.use_imap and self.use_starttls and not self.use_ssl)
		incoming_conn = conn_method(self.email_server, port=self.incoming_port)
		incoming_conn.logout() if self.use_imap else incoming_conn.quit()

	@handle_error("outgoing")
	def validate_outgoing_server_conn(self):
		conn_method = smtplib.SMTP

		if self.use_ssl_for_outgoing:
			self.smtp_port = self.smtp_port or 465
			conn_method = smtplib.SMTP_SSL
		elif self.use_tls:
			self.smtp_port = self.smtp_port or 587

		conn_method((self.smtp_server or ""), cint(self.smtp_port) or 0).quit()
