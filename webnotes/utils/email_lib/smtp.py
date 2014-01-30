# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes	
import smtplib
import _socket
from webnotes.utils import cint

def send(email, as_bulk=False):
	"""send the message or add it to Outbox Email"""
	if webnotes.flags.mute_emails or webnotes.conf.get("mute_emails") or False:
		webnotes.msgprint("Emails are muted")
		return
	
	
	try:
		smtpserver = SMTPServer()
		if hasattr(smtpserver, "always_use_login_id_as_sender") and \
			cint(smtpserver.always_use_login_id_as_sender) and smtpserver.login:
			if not email.reply_to:
				email.reply_to = email.sender
			email.sender = smtpserver.login
		
		smtpserver.sess.sendmail(email.sender, email.recipients + (email.cc or []),
			email.as_string())
			
	except smtplib.SMTPSenderRefused:
		webnotes.msgprint("""Invalid Outgoing Mail Server's Login Id or Password. \
			Please rectify and try again.""")
		raise
	except smtplib.SMTPRecipientsRefused:
		webnotes.msgprint("""Invalid Recipient (To) Email Address. \
			Please rectify and try again.""")
		raise

class SMTPServer:
	def __init__(self, login=None, password=None, server=None, port=None, use_ssl=None):
		# get defaults from control panel
		try:
			es = webnotes.doc('Email Settings','Email Settings')
		except webnotes.DoesNotExistError:
			es = None
		
		self._sess = None
		if server:
			self.server = server
			self.port = port
			self.use_ssl = cint(use_ssl)
			self.login = login
			self.password = password
		elif es and es.outgoing_mail_server:
			self.server = es.outgoing_mail_server
			self.port = es.mail_port
			self.use_ssl = cint(es.use_ssl)
			self.login = es.mail_login
			self.password = es.mail_password
			self.always_use_login_id_as_sender = es.always_use_login_id_as_sender
		else:
			self.server = webnotes.conf.get("mail_server") or ""
			self.port = webnotes.conf.get("mail_port") or None
			self.use_ssl = cint(webnotes.conf.get("use_ssl") or 0)
			self.login = webnotes.conf.get("mail_login") or ""
			self.password = webnotes.conf.get("mail_password") or ""
			
	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess
		
		# check if email server specified
		if not self.server:
			err_msg = 'Outgoing Mail Server not specified'
			webnotes.msgprint(err_msg)
			raise webnotes.OutgoingEmailError, err_msg
		
		try:
			if self.use_ssl and not self.port:
				self.port = 587
			
			self._sess = smtplib.SMTP((self.server or "").encode('utf-8'), 
				cint(self.port) or None)
			
			if not self._sess:
				err_msg = 'Could not connect to outgoing email server'
				webnotes.msgprint(err_msg)
				raise webnotes.OutgoingEmailError, err_msg
		
			if self.use_ssl: 
				self._sess.ehlo()
				self._sess.starttls()
				self._sess.ehlo()

			if self.login:
				ret = self._sess.login((self.login or "").encode('utf-8'), 
					(self.password or "").encode('utf-8'))

				# check if logged correctly
				if ret[0]!=235:
					webnotes.msgprint(ret[1])
					raise webnotes.OutgoingEmailError, ret[1]

			return self._sess
			
		except _socket.error:
			# Invalid mail server -- due to refusing connection
			webnotes.msgprint('Invalid Outgoing Mail Server or Port. Please rectify and try again.')
			raise
		except smtplib.SMTPAuthenticationError:
			webnotes.msgprint("Invalid Outgoing Mail Server's Login Id or Password. \
				Please rectify and try again.")
			raise
		except smtplib.SMTPException:
			webnotes.msgprint('There is something wrong with your Outgoing Mail Settings. \
				Please contact us at support@erpnext.com')
			raise
	
