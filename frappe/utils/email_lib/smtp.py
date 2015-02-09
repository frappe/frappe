# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import smtplib
import _socket
from frappe.utils import cint
from frappe import _

def send(email, as_bulk=False):
	"""send the message or add it to Outbox Email"""
	if frappe.flags.mute_emails or frappe.conf.get("mute_emails") or False:
		frappe.msgprint(_("Emails are muted"))
		return

	email.validate()

	try:
		smtpserver = SMTPServer()
		if hasattr(smtpserver, "always_use_login_id_as_sender") and \
			cint(smtpserver.always_use_login_id_as_sender) and smtpserver.login:
			if not email.reply_to:
				email.reply_to = email.sender
			email.sender = smtpserver.login

		smtpserver.sess.sendmail(email.sender.encode("utf-8"),
			[e.encode("utf-8") for e in (email.recipients + (email.cc or []))],
			email.as_string())

	except smtplib.SMTPSenderRefused:
		frappe.msgprint(_("Invalid login or password"))
		raise
	except smtplib.SMTPRecipientsRefused:
		frappe.msgprint(_("Invalid recipient address"))
		raise

class SMTPServer:
	def __init__(self, login=None, password=None, server=None, port=None, use_ssl=None):
		# get defaults from mail settings
		try:
			self.email_settings = frappe.get_doc('Outgoing Email Settings', 'Outgoing Email Settings')
		except frappe.DoesNotExistError:
			self.email_settings = None

		self._sess = None
		if server:
			self.server = server
			self.port = port
			self.use_ssl = cint(use_ssl)
			self.login = login
			self.password = password
		elif self.email_settings and cint(self.email_settings.enabled):
			self.server = self.email_settings.mail_server
			self.port = self.email_settings.mail_port
			self.use_ssl = cint(self.email_settings.use_ssl)
			self.login = self.email_settings.mail_login
			self.password = self.email_settings.mail_password
			self.always_use_login_id_as_sender = self.email_settings.always_use_login_id_as_sender
		else:
			self.server = frappe.conf.get("mail_server") or ""
			self.port = frappe.conf.get("mail_port") or None
			self.use_ssl = cint(frappe.conf.get("use_ssl") or 0)
			self.login = frappe.conf.get("mail_login") or ""
			self.password = frappe.conf.get("mail_password") or ""

	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess

		# check if email server specified
		if not self.server:
			err_msg = _('Outgoing Mail Server not specified')
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

			if self.login:
				ret = self._sess.login((self.login or "").encode('utf-8'),
					(self.password or "").encode('utf-8'))

				# check if logged correctly
				if ret[0]!=235:
					frappe.msgprint(ret[1])
					raise frappe.OutgoingEmailError, ret[1]

			return self._sess

		except _socket.error:
			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_('Invalid Outgoing Mail Server or Port'))
			raise
		except smtplib.SMTPAuthenticationError:
			frappe.msgprint(_("Invalid login or password"))
			raise
		except smtplib.SMTPException:
			frappe.msgprint(_('Unable to send emails at this time'))
			raise

