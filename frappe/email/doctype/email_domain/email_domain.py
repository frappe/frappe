# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address ,cint, cstr
import imaplib,poplib,smtplib
from frappe.email.utils import get_port

class EmailDomain(Document):
	def autoname(self):
		if self.domain_name:
			self.name = self.domain_name

	def validate(self):
		"""Validate email id and check POP3/IMAP and SMTP connections is enabled."""
		logger = frappe.logger()

		if self.email_id:
			validate_email_address(self.email_id, True)

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		if not frappe.local.flags.in_install and not frappe.local.flags.in_patch:
			try:
				if self.use_imap:
					logger.info('Checking incoming IMAP email server {host}:{port} ssl={ssl}...'.format(
						host=self.email_server, port=get_port(self), ssl=self.use_ssl))
					if self.use_ssl:
						test = imaplib.IMAP4_SSL(self.email_server, port=get_port(self))
					else:
						test = imaplib.IMAP4(self.email_server, port=get_port(self))

				else:
					logger.info('Checking incoming POP3 email server {host}:{port} ssl={ssl}...'.format(
						host=self.email_server, port=get_port(self), ssl=self.use_ssl))
					if self.use_ssl:
						test = poplib.POP3_SSL(self.email_server, port=get_port(self))
					else:
						test = poplib.POP3(self.email_server, port=get_port(self))

			except Exception as e:
				logger.warn('Incoming email account "{host}" not correct'.format(host=self.email_server), exc_info=e)
				frappe.throw(title=_("Incoming email account not correct"),
					msg='Error connecting IMAP/POP3 "{host}": {e}'.format(host=self.email_server, e=e))

			finally:
				try:
					if self.use_imap:
						test.logout()
					else:
						test.quit()
				except Exception:
					pass

			try:
				if self.get('use_ssl_for_outgoing'):
					if not self.get('smtp_port'):
						self.smtp_port = 465

					logger.info('Checking outgoing SMTPS email server {host}:{port}...'.format(
						host=self.smtp_server, port=self.smtp_port))
					sess = smtplib.SMTP_SSL((self.smtp_server or "").encode('utf-8'),
							cint(self.smtp_port) or None)
				else:
					if self.use_tls and not self.smtp_port:
						self.smtp_port = 587
					logger.info('Checking outgoing SMTP email server {host}:{port} STARTTLS={tls}...'.format(
						host=self.smtp_server, port=self.get('smtp_port'), tls=self.use_tls))
					sess = smtplib.SMTP(cstr(self.smtp_server or ""), cint(self.smtp_port) or None)
				sess.quit()
			except Exception as e:
				logger.warn('Outgoing email account "{host}" not correct'.format(host=self.smtp_server), exc_info=e)
				frappe.throw(title=_("Outgoing email account not correct"),
					msg='Error connecting SMTP "{host}": {e}'.format(host=self.smtp_server, e=e))

	def on_update(self):
		"""update all email accounts using this domain"""
		for email_account in frappe.get_all("Email Account", filters={"domain": self.name}):
			try:
				email_account = frappe.get_doc("Email Account", email_account.name)
				for attr in ["email_server", "use_imap", "use_ssl", "use_tls", "attachment_limit", "smtp_server", "smtp_port", "use_ssl_for_outgoing", "append_emails_to_sent_folder", "incoming_port"]:
					email_account.set(attr, self.get(attr, default=0))
				email_account.save()

			except Exception as e:
				frappe.msgprint(_("Error has occurred in {0}").format(email_account.name), raise_exception=e.__class__)
