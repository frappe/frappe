# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import smtplib
import email.utils
import _socket, sys
from frappe import _
from frappe.utils import cint, cstr, parse_addr

CONNECTION_FAILED = _('Could not connect to outgoing email server')
AUTH_ERROR_TITLE = _("Invalid Credentials")
AUTH_ERROR = _("Incorrect email or password. Please check your login credentials.")
SOCKET_ERROR_TITLE = _("Incorrect Configuration")
SOCKET_ERROR = _("Invalid Outgoing Mail Server or Port")
SEND_MAIL_FAILED = _("Unable to send emails at this time")
EMAIL_ACCOUNT_MISSING = _('Email Account not setup. Please create a new Email Account from Setup > Email > Email Account')

class InvalidEmailCredentials(frappe.ValidationError):
	pass

def send(email, append_to=None, retry=1):
	"""Deprecated: Send the message or add it to Outbox Email"""
	def _send(retry):
		from frappe.email.doctype.email_account.email_account import EmailAccount
		try:
			email_account = EmailAccount.find_outgoing(match_by_doctype=append_to)
			smtpserver = email_account.get_smtp_server()

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
	def __init__(self, server, login=None, password=None, port=None, use_tls=None, use_ssl=None):
		self.login = login
		self.password = password
		self._server = server
		self._port = port
		self.use_tls = use_tls
		self.use_ssl = use_ssl
		self._session = None

		if not self.server:
			frappe.msgprint(EMAIL_ACCOUNT_MISSING, raise_exception=frappe.OutgoingEmailError)

	@property
	def port(self):
		port = self._port or (self.use_ssl and 465) or (self.use_tls and 587)
		return cint(port)

	@property
	def server(self):
		return cstr(self._server or "")

	def secure_session(self, conn):
		"""Secure the connection incase of TLS.
		"""
		if self.use_tls:
			conn.ehlo()
			conn.starttls()
			conn.ehlo()

	@property
	def session(self):
		if self.is_session_active():
			return self._session

		SMTP = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

		try:
			_session = SMTP(self.server, self.port)
			if not _session:
				frappe.msgprint(CONNECTION_FAILED, raise_exception=frappe.OutgoingEmailError)

			self.secure_session(_session)
			if self.login and self.password:
				res = _session.login(str(self.login or ""), str(self.password or ""))

				# check if logged correctly
				if res[0]!=235:
					frappe.msgprint(res[1], raise_exception=frappe.OutgoingEmailError)

			self._session = _session
			return self._session

		except smtplib.SMTPAuthenticationError as e:
			self.throw_invalid_credentials_exception()

		except _socket.error as e:
			# Invalid mail server -- due to refusing connection
			frappe.throw(SOCKET_ERROR, title=SOCKET_ERROR_TITLE)

		except smtplib.SMTPException:
			frappe.msgprint(SEND_MAIL_FAILED)
			raise

	def is_session_active(self):
		if self._session:
			try:
				return self._session.noop()[0] == 250
			except Exception:
				return False

	def quit(self):
		if self.is_session_active():
			self._session.quit()

	@classmethod
	def throw_invalid_credentials_exception(cls):
		frappe.throw(AUTH_ERROR, title=AUTH_ERROR_TITLE, exc=InvalidEmailCredentials)
