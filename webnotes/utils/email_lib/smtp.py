# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
"""
Sends email via outgoing server specified in "Control Panel"
Allows easy adding of Attachments of "File" objects
"""

import webnotes	
import conf
from webnotes import msgprint
import email

def get_email(recipients, sender='', msg='', subject='[No Subject]', text_content = None):
	"""send an html email as multipart with attachments and all"""
	email = EMail(sender, recipients, subject)
	if (not '<br>' in msg) and (not '<p>' in msg) and (not '<div' in msg):
		msg = msg.replace('\n', '<br>')
	email.set_html(msg, text_content)

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
	
	def set_html(self, message, text_content = None):

		"""Attach message in the html portion of multipart/alternative"""
		message = message + self.get_footer()

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
	
	def get_footer(self):
		"""append a footer (signature)"""
		import startup
		
		footer = ""
		# if self.sender == webnotes.session.user:
		# 	signature = webnotes.conn.get_value("Profile", self.sender, "email_signature") or ""
		# 	if signature and (not "<br>" in signature) and (not "<p" in signature) \
		# 		and not "<div" in signature:
		# 		signature = signature.replace("\n", "<br>\n")
		# 	footer = signature
		
		footer += webnotes.conn.get_value('Control Panel',None,'mail_footer') or ''
		footer += getattr(startup, 'mail_footer', '')
		
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
			part = MIMEText(fcontent, _subtype=subtype, _charset='utf-8')
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
		from webnotes.utils import validate_email_add, extract_email_id
		def _validate(email):
			"""validate an email field"""
			if email:
				if not validate_email_add(email):
					# try extracting the email part and set as sender
					new_email = extract_email_id(email)
					if not (new_email and validate_email_add(new_email)):
						webnotes.msgprint("%s is not a valid email id" % email,
							raise_exception = 1)
					email = new_email
			return email
		
		if not self.sender:
			# TODO: remove erpnext id
			self.sender = webnotes.conn.get_value('Email Settings', None,
				'auto_email_id') or getattr(conf, 'auto_email_id', 
					'ERPNext Notification <notification@erpnext.com>')
				
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
		import smtplib
		try:
			SMTPServer().sess.sendmail(self.sender, self.recipients + (self.cc or []),
				self.as_string())
		except smtplib.SMTPSenderRefused, e:
			webnotes.msgprint("""Invalid Outgoing Mail Server's Login Id or Password. \
				Please rectify and try again.""",
				raise_exception=webnotes.OutgoingEmailError)

class SMTPServer:
	def __init__(self, login=None, password=None, server=None, port=None, use_ssl=None):
		import webnotes.model.doc
		from webnotes.utils import cint

		# get defaults from control panel
		es = webnotes.model.doc.Document('Email Settings','Email Settings')
		
		self._sess = None
		if server:
			self.server = server
			self.port = port
			self.use_ssl = cint(use_ssl)
			self.login = login
			self.password = password
		elif es.outgoing_mail_server:
			self.server = es.outgoing_mail_server
			self.port = es.mail_port
			self.use_ssl = cint(es.use_ssl)
			self.login = es.mail_login
			self.password = es.mail_password
		else:
			self.server = getattr(conf, "mail_server", "")
			self.port = getattr(conf, "mail_port", None)
			self.use_ssl = cint(getattr(conf, "use_ssl", 0))
			self.login = getattr(conf, "mail_login", "")
			self.password = getattr(conf, "mail_password", "")
			
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
			
		except _socket.error, e:
			# Invalid mail server -- due to refusing connection
			webnotes.msgprint('Invalid Outgoing Mail Server or Port. Please rectify and try again.')
			raise webnotes.OutgoingEmailError, e
		except smtplib.SMTPAuthenticationError, e:
			webnotes.msgprint("Invalid Outgoing Mail Server's Login Id or Password. \
				Please rectify and try again.")
			raise webnotes.OutgoingEmailError, e
		except smtplib.SMTPException, e:
			webnotes.msgprint('There is something wrong with your Outgoing Mail Settings. \
				Please contact us at support@erpnext.com')
			raise webnotes.OutgoingEmailError, e

	
