# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
Sends email via outgoing server specified in "Control Panel"
Allows easy adding of Attachments of "File" objects
"""

import webnotes	
from webnotes import conf
from webnotes import msgprint
from webnotes.utils import cint, expand_partial_links

class OutgoingEmailError(webnotes.ValidationError): pass

def get_email(recipients, sender='', msg='', subject='[No Subject]', text_content = None, footer=None):
	"""send an html email as multipart with attachments and all"""
	email = EMail(sender, recipients, subject)
	if (not '<br>' in msg) and (not '<p>' in msg) and (not '<div' in msg):
		msg = msg.replace('\n', '<br>')
	email.set_html(msg, text_content, footer=footer)

	return email

class EMail:
	"""
	Wrapper on the email module. Email object represents emails to be sent to the client. 
	Also provides a clean way to add binary `FileData` attachments
	Also sets all messages as multipart/alternative for cleaner reading in text-only clients
	"""
	def __init__(self, sender='', recipients=[], subject='', alternative=0, reply_to=None):
		from email.mime.multipart import MIMEMultipart
		from email import Charset
		Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

		if isinstance(recipients, basestring):
			recipients = recipients.replace(';', ',').replace('\n', '')
			recipients = recipients.split(',')
		
		# remove null
		recipients = filter(None, (r.strip() for r in recipients))
		
		self.sender = sender
		self.reply_to = reply_to or sender
		self.recipients = recipients
		self.subject = subject
		
		self.msg_root = MIMEMultipart('mixed')
		self.msg_multipart = MIMEMultipart('alternative')
		self.msg_root.attach(self.msg_multipart)
		self.cc = []
		self.html_set = False
	
	def set_html(self, message, text_content = None, footer=None):
		"""Attach message in the html portion of multipart/alternative"""
		message = message + self.get_footer(footer)
		message = expand_partial_links(message)

		# this is the first html part of a multi-part message, 
		# convert to text well
		if not self.html_set:
			if text_content:
				self.set_text(text_content)
			else:
				self.set_html_as_text(message)
		
		self.set_part_html(message)
		self.html_set = True
		
	def set_text(self, message):
		"""
			Attach message in the text portion of multipart/alternative
		"""
		from email.mime.text import MIMEText
		part = MIMEText(message.encode('utf-8'), 'plain', 'utf-8')		
		self.msg_multipart.attach(part)
			
	def set_part_html(self, message):
		from email.mime.text import MIMEText
		part = MIMEText(message.encode('utf-8'), 'html', 'utf-8')
		self.msg_multipart.attach(part)

	def set_html_as_text(self, html):
		"""return html2text"""
		import HTMLParser
		from webnotes.utils.email_lib.html2text import html2text
		try:
			self.set_text(html2text(html))
		except HTMLParser.HTMLParseError:
			pass
	
	def set_message(self, message, mime_type='text/html', as_attachment=0, filename='attachment.html'):
		"""Append the message with MIME content to the root node (as attachment)"""
		from email.mime.text import MIMEText
		
		maintype, subtype = mime_type.split('/')
		part = MIMEText(message, _subtype = subtype)
		
		if as_attachment:
			part.add_header('Content-Disposition', 'attachment', filename=filename)
		
		self.msg_root.attach(part)
	
	def get_footer(self, footer=None):
		"""append a footer (signature)"""		
		footer = footer or ""
		footer += webnotes.conn.get_value('Control Panel',None,'mail_footer') or ''

		other_footers = webnotes.get_hooks().mail_footer or []
		
		for f in other_footers:
			footer += f
		
		return footer
		
	def attach_file(self, n):
		"""attach a file from the `FileData` table"""
		from webnotes.utils.file_manager import get_file		
		res = get_file(n)
		if not res:
			return
		
		self.add_attachment(res[0], res[1])
	
	def add_attachment(self, fname, fcontent, content_type=None):
		"""add attachment"""
		from email.mime.audio import MIMEAudio
		from email.mime.base import MIMEBase
		from email.mime.image import MIMEImage
		from email.mime.text import MIMEText
					
		import mimetypes
		if not content_type:
			content_type, encoding = mimetypes.guess_type(fname)

		if content_type is None:
			# No guess could be made, or the file is encoded (compressed), so
			# use a generic bag-of-bits type.
			content_type = 'application/octet-stream'
		
		maintype, subtype = content_type.split('/', 1)
		if maintype == 'text':
			# Note: we should handle calculating the charset
			if isinstance(fcontent, unicode):
				fcontent = fcontent.encode("utf-8")
			part = MIMEText(fcontent, _subtype=subtype, _charset="utf-8")
		elif maintype == 'image':
			part = MIMEImage(fcontent, _subtype=subtype)
		elif maintype == 'audio':
			part = MIMEAudio(fcontent, _subtype=subtype)
		else:
			part = MIMEBase(maintype, subtype)
			part.set_payload(fcontent)
			# Encode the payload using Base64
			from email import encoders
			encoders.encode_base64(part)
			
		# Set the filename parameter
		if fname:
			part.add_header(b'Content-Disposition',
				("attachment; filename=%s" % fname).encode('utf-8'))

		self.msg_root.attach(part)
	
	def validate(self):
		"""validate the email ids"""
		from webnotes.utils import validate_email_add
		def _validate(email):
			"""validate an email field"""
			if email and not validate_email_add(email):
				webnotes.msgprint("%s is not a valid email id" % email,
					raise_exception = 1)
			return email
		
		if not self.sender:
			self.sender = webnotes.conn.get_value('Email Settings', None,
				'auto_email_id') or conf.get('auto_email_id') or None
			if not self.sender:
				webnotes.msgprint("""Please specify 'Auto Email Id' \
					in Setup > Email Settings""")
				if not "expires_on" in conf:
					webnotes.msgprint("""Alternatively, \
						you can also specify 'auto_email_id' in conf.py""")
				raise webnotes.ValidationError
				
		self.sender = _validate(self.sender)
		self.reply_to = _validate(self.reply_to)
		
		for e in self.recipients + (self.cc or []):
			_validate(e.strip())
	
	def make(self):
		"""build into msg_root"""
		self.msg_root['Subject'] = self.subject.encode("utf-8")
		self.msg_root['From'] = self.sender.encode("utf-8")
		self.msg_root['To'] = ', '.join([r.strip() for r in self.recipients]).encode("utf-8")
		if self.reply_to and self.reply_to != self.sender:
			self.msg_root['Reply-To'] = self.reply_to.encode("utf-8")
		
		if self.cc:
			self.msg_root['CC'] = ', '.join([r.strip() for r in self.cc]).encode("utf-8")
	
	def as_string(self):
		"""validate, build message and convert to string"""
		self.validate()
		self.make()
		return self.msg_root.as_string()
		
	def send(self, as_bulk=False):
		"""send the message or add it to Outbox Email"""
		if webnotes.flags.mute_emails or conf.get("mute_emails") or False:
			webnotes.msgprint("Emails are muted")
			return
		
		
		import smtplib
		try:
			smtpserver = SMTPServer()
			if hasattr(smtpserver, "always_use_login_id_as_sender") and \
				cint(smtpserver.always_use_login_id_as_sender) and smtpserver.login:
				self.sender = smtpserver.login
			
			smtpserver.sess.sendmail(self.sender, self.recipients + (self.cc or []),
				self.as_string())
				
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
		import webnotes.model.doc
		from webnotes.utils import cint

		# get defaults from control panel
		try:
			es = webnotes.model.doc.Document('Email Settings','Email Settings')
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
			self.server = conf.get("mail_server") or ""
			self.port = conf.get("mail_port") or None
			self.use_ssl = cint(conf.get("use_ssl") or 0)
			self.login = conf.get("mail_login") or ""
			self.password = conf.get("mail_password") or ""
			
	@property
	def sess(self):
		"""get session"""
		if self._sess:
			return self._sess
		
		from webnotes.utils import cint
		import smtplib
		import _socket
		
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
					msgprint(ret[1])
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
	
