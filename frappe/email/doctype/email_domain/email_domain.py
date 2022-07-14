# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import smtplib

import frappe
from frappe import _
from frappe.email.receive import Timed_IMAP4, Timed_IMAP4_SSL, Timed_POP3, Timed_POP3_SSL
from frappe.email.utils import get_port
from frappe.model.document import Document
from frappe.utils import cint


class EmailDomain(Document):
	def validate(self):
		"""Validate email id and check POP3/IMAP and SMTP connections is enabled."""

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		if not frappe.local.flags.in_install and not frappe.local.flags.in_patch:
			self.logger = frappe.logger()
			self.validate_incoming_server_conn()
			self.validate_outgoing_server_conn()

	def on_update(self):
		"""update all email accounts using this domain"""
		for email_account in frappe.get_all("Email Account", filters={"domain": self.name}):
			try:
				email_account = frappe.get_doc("Email Account", email_account.name)
				for attr in [
					"email_server",
					"use_imap",
					"use_ssl",
					"use_tls",
					"attachment_limit",
					"smtp_server",
					"smtp_port",
					"use_ssl_for_outgoing",
					"append_emails_to_sent_folder",
					"incoming_port",
				]:
					email_account.set(attr, self.get(attr, default=0))
				email_account.save()

			except Exception as e:
				frappe.msgprint(
					_("Error has occurred in {0}").format(email_account.name), raise_exception=e.__class__
				)

	def validate_incoming_server_conn(self):
		self.incoming_port = get_port(self)

		try:
			if self.use_imap:
				self.logger.info(
					"Checking incoming IMAP email server {host}:{port} ssl={ssl}...".format(
						host=self.email_server, port=self.incoming_port, ssl=self.use_ssl
					)
				)

				smtp_method = Timed_IMAP4_SSL if self.use_ssl else Timed_IMAP4
				incoming_server = smtp_method(self.email_server, port=self.incoming_port)
				incoming_server.logout()
			else:
				self.logger.info(
					"Checking incoming POP3 email server {host}:{port} ssl={ssl}...".format(
						host=self.email_server, port=self.incoming_port, ssl=self.use_ssl
					)
				)

				pop_method = Timed_POP3_SSL if self.use_ssl else Timed_POP3
				incoming_server = pop_method(self.email_server, port=self.incoming_port)
				incoming_server.quit()
		except Exception as e:
			self.logger.warn(f'Incoming email server "{self.email_server}" not correct', exc_info=e)
			frappe.throw(
				title=_("Incoming email server not correct"),
				msg=f'Error connecting IMAP/POP3 "{self.email_server}": {e}',
			)

	def validate_outgoing_server_conn(self):
		try:
			if self.use_ssl_for_outgoing:
				if not self.smtp_port:
					self.smtp_port = 465

				self.logger.info(
					"Checking outgoing SMTPS email server {host}:{port}...".format(
						host=self.smtp_server, port=self.smtp_port
					)
				)
				outgoing_server = smtplib.SMTP_SSL((self.smtp_server or ""), cint(self.smtp_port) or 0)
			else:
				if self.use_tls and not self.smtp_port:
					self.smtp_port = 587

				self.logger.info(
					"Checking outgoing SMTP email server {host}:{port} STARTTLS={tls}...".format(
						host=self.smtp_server, port=self.get("smtp_port"), tls=self.use_tls
					)
				)

				outgoing_server = smtplib.SMTP((self.smtp_server or ""), cint(self.smtp_port) or 0)

			outgoing_server.quit()
		except Exception as e:
			self.logger.warn(f'Outgoing email server "{self.smtp_server}" not correct', exc_info=e)
			frappe.throw(
				title=_("Outgoing email server not correct"),
				msg=f'Error connecting SMTP "{self.smtp_server}": {e}',
			)
