# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import smtplib
import email.utils
import _socket
from frappe.utils import cint
from frappe import _

def send(email, append_to=None):
	"""send the message or add it to Outbox Email"""
	if frappe.flags.in_test:
		frappe.flags.sent_mail = email.as_string()
		return

	if frappe.are_emails_muted():
		frappe.msgprint(_("Emails are muted"))
		return

	try:
		smtpserver = SMTPServer(append_to=append_to)
		if hasattr(smtpserver, "always_use_account_email_id_as_sender") and \
			cint(smtpserver.always_use_account_email_id_as_sender) and smtpserver.login:
			if not email.reply_to:
				email.reply_to = email.sender
			email.sender = smtpserver.login

		smtpserver.sess.sendmail(email.sender, email.recipients + (email.cc or []),
			email.as_string())

	except smtplib.SMTPSenderRefused:
		frappe.msgprint(_("Invalid login or password"))
		raise
	except smtplib.SMTPRecipientsRefused:
		frappe.msgprint(_("Invalid recipient address"))
		raise

def get_outgoing_email_account(raise_exception_not_set=True, append_to=None):
	"""Returns outgoing email account based on `append_to` or the default
		outgoing account. If default outgoing account is not found, it will
		try getting settings from `site_config.json`."""

	if not getattr(frappe.local, "outgoing_email_account", None):
		frappe.local.outgoing_email_account = {}

	if not frappe.local.outgoing_email_account.get(append_to or "default"):
		email_account = None

		if append_to:
			email_account = _get_email_account({"enable_outgoing": 1, "append_to": append_to})

		if not email_account:
			email_account = get_default_outgoing_email_account(raise_exception_not_set=raise_exception_not_set)

		if not email_account and raise_exception_not_set:
			frappe.throw(_("Please setup default Email Account from Setup > Email > Email Account"),
				frappe.OutgoingEmailError)

		if email_account:
			email_account.default_sender = email.utils.formataddr((email_account.name,
				email_account.get("sender") or email_account.get("email_id")))

		frappe.local.outgoing_email_account[append_to or "default"] = email_account

	return frappe.local.outgoing_email_account[append_to or "default"]

def get_default_outgoing_email_account(raise_exception_not_set=True):
	email_account = _get_email_account({"enable_outgoing": 1, "default_outgoing": 1})

	if not email_account and frappe.conf.get("mail_server"):
		# from site_config.json
		email_account = frappe.new_doc("Email Account")
		email_account.update({
			"smtp_server": frappe.conf.get("mail_server"),
			"smtp_port": frappe.conf.get("mail_port"),
			"use_tls": cint(frappe.conf.get("use_ssl") or 0),
			"email_id": frappe.conf.get("mail_login"),
			"password": frappe.conf.get("mail_password"),
			"sender": frappe.conf.get("auto_email_id", "notifications@example.com")
		})
		email_account.from_site_config = True
		email_account.name = frappe.conf.get("email_sender_name") or "Frappe"

	if not email_account and not raise_exception_not_set:
		return None

	if frappe.are_emails_muted():
		# create a stub
		email_account = frappe.new_doc("Email Account")
		email_account.update({
			"sender": "notifications@example.com"
		})

	return email_account

def _get_email_account(filters):
	name = frappe.db.get_value("Email Account", filters)
	return frappe.get_doc("Email Account", name) if name else None

class SMTPServer:
	def __init__(self, login=None, password=None, server=None, port=None, use_ssl=None, append_to=None):
		# get defaults from mail settings

		self._sess = None
		self.email_account = None
		self.server = None
		if server:
			self.server = server
			self.port = port
			self.use_ssl = cint(use_ssl)
			self.login = login
			self.password = password

		else:
			self.setup_email_account(append_to)

	def setup_email_account(self, append_to=None):
		self.email_account = get_outgoing_email_account(raise_exception_not_set=False, append_to=append_to)
		if self.email_account:
			self.server = self.email_account.smtp_server
			self.login = getattr(self.email_account, "login_id", None) \
				or self.email_account.email_id
			self.password = self.email_account.password
			self.port = self.email_account.smtp_port
			self.use_ssl = self.email_account.use_tls
			self.sender = self.email_account.email_id
			self.always_use_account_email_id_as_sender = self.email_account.get("always_use_account_email_id_as_sender")

	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess

		# check if email server specified
		if not getattr(self, 'server'):
			err_msg = _('Email Account not setup. Please create a new Email Account from Setup > Email > Email Account')
			frappe.msgprint(err_msg)
			raise frappe.OutgoingEmailError, err_msg

		try:
			if self.use_ssl and not self.port:
				self.port = 587

			self._sess = smtplib.SMTP((self.server or "").encode('utf-8'),
				cint(self.port) or None)

			if not self._sess:
				err_msg = _('Could not connect to outgoing email server')
				frappe.msgprint(err_msg)
				raise frappe.OutgoingEmailError, err_msg

			if self.use_ssl:
				self._sess.ehlo()
				self._sess.starttls()
				self._sess.ehlo()

			if self.login and self.password:
				ret = self._sess.login((self.login or "").encode('utf-8'),
					(self.password or "").encode('utf-8'))

				# check if logged correctly
				if ret[0]!=235:
					frappe.msgprint(ret[1])
					raise frappe.OutgoingEmailError, ret[1]

			return self._sess

		except _socket.error:
			# Invalid mail server -- due to refusing connection
			frappe.throw(_('Invalid Outgoing Mail Server or Port'))
		except smtplib.SMTPAuthenticationError:
			frappe.throw(_("Invalid login or password"))
		except smtplib.SMTPException:
			frappe.msgprint(_('Unable to send emails at this time'))
			raise
