# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import smtplib
import email.utils
import _socket, sys
from frappe import _
from frappe.utils import cint, cstr, parse_addr

def send(email, append_to=None, retry=1):
	"""Deprecated: Send the message or add it to Outbox Email"""
	def _send(retry):
		try:
			smtpserver = SMTPServer(append_to=append_to)

			# validate is called in as_string
			email_body = email.as_string()

			smtpserver.sess.sendmail(email.sender, email.recipients + (email.cc or []), email_body)
		except smtplib.SMTPSenderRefused:
			frappe.throw(_("Invalid login or password"), title='Email Failed')
			raise
		except smtplib.SMTPRecipientsRefused:
			frappe.msgprint(_("Invalid recipient address"), title='Email Failed')
			raise
		except (smtplib.SMTPServerDisconnected, smtplib.SMTPAuthenticationError):
			if not retry:
				raise
			else:
				retry = retry - 1
				_send(retry)

	_send(retry)


class SMTPServer:
	def __init__(self, login=None, password=None, server=None, port=None, use_tls=None, use_ssl=None, append_to=None):
		# get defaults from mail settings

		self._sess = None
		self.email_account = None
		self.server = None
		self.append_emails_to_sent_folder = None

		if server:
			self.server = server
			self.port = port
			self.use_tls = cint(use_tls)
			self.use_ssl = cint(use_ssl)
			self.login = login
			self.password = password

		else:
			self.setup_email_account(append_to)

	def setup_email_account(self, append_to=None, sender=None):
		from frappe.email.doctype.email_account.email_account import EmailAccount
		self.email_account = EmailAccount.find_outgoing(match_by_doctype=append_to, match_by_email=sender)
		if self.email_account:
			self.server = self.email_account.smtp_server
			self.login = (getattr(self.email_account, "login_id", None) or self.email_account.email_id)
			if self.email_account.no_smtp_authentication or frappe.local.flags.in_test:
				self.password = None
			else:
				self.password = self.email_account._password
			self.port = self.email_account.smtp_port
			self.use_tls = self.email_account.use_tls
			self.sender = self.email_account.email_id
			self.use_ssl = self.email_account.use_ssl_for_outgoing
			self.append_emails_to_sent_folder = self.email_account.append_emails_to_sent_folder
			self.always_use_account_email_id_as_sender = cint(self.email_account.get("always_use_account_email_id_as_sender"))
			self.always_use_account_name_as_sender_name = cint(self.email_account.get("always_use_account_name_as_sender_name"))

	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess

		# check if email server specified
		if not getattr(self, 'server'):
			err_msg = _('Email Account not setup. Please create a new Email Account from Setup > Email > Email Account')
			frappe.msgprint(err_msg)
			raise frappe.OutgoingEmailError(err_msg)

		try:
			if self.use_ssl:
				if not self.port:
					self.port = 465

				self._sess = smtplib.SMTP_SSL((self.server or ""), cint(self.port))
			else:
				if self.use_tls and not self.port:
					self.port = 587

				self._sess = smtplib.SMTP(cstr(self.server or ""),
						cint(self.port) or None)

			if not self._sess:
				err_msg = _('Could not connect to outgoing email server')
				frappe.msgprint(err_msg)
				raise frappe.OutgoingEmailError(err_msg)

			if self.use_tls:
				self._sess.ehlo()
				self._sess.starttls()
				self._sess.ehlo()

			if self.login and self.password:
				ret = self._sess.login(str(self.login or ""), str(self.password or ""))

				# check if logged correctly
				if ret[0]!=235:
					frappe.msgprint(ret[1])
					raise frappe.OutgoingEmailError(ret[1])

			return self._sess

		except smtplib.SMTPAuthenticationError as e:
			from frappe.email.doctype.email_account.email_account import EmailAccount
			EmailAccount.throw_invalid_credentials_exception()

		except _socket.error as e:
			# Invalid mail server -- due to refusing connection
			frappe.throw(
				_("Invalid Outgoing Mail Server or Port"),
				exc=frappe.ValidationError,
				title=_("Incorrect Configuration")
			)

		except smtplib.SMTPException:
			frappe.msgprint(_('Unable to send emails at this time'))
			raise
