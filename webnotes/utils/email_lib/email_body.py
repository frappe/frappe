# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes	

from webnotes.utils import scrub_urls
import email.utils
from inlinestyler.utils import inline_css

def get_email(recipients, sender='', msg='', subject='[No Subject]', 
	text_content = None, footer=None, formatted=None):
	"""send an html email as multipart with attachments and all"""
	email = EMail(sender, recipients, subject)
	if (not '<br>' in msg) and (not '<p>' in msg) and (not '<div' in msg):
		msg = msg.replace('\n', '<br>')
	email.set_html(msg, text_content, footer=footer, formatted=formatted)

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
	
	def set_html(self, message, text_content = None, footer=None, formatted=None):
		"""Attach message in the html portion of multipart/alternative"""
		if not formatted:
			formatted = get_formatted_html(self.subject, message, footer)
		
		# this is the first html part of a multi-part message, 
		# convert to text well
		if not self.html_set:
			if text_content:
				self.set_text(text_content)
			else:
				self.set_html_as_text(message)
		
		self.set_part_html(formatted)
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
				'auto_email_id') or webnotes.conf.get('auto_email_id') or None
			if not self.sender:
				webnotes.msgprint("""Please specify 'Auto Email Id' \
					in Setup > Email Settings""")
				if not "expires_on" in webnotes.conf:
					webnotes.msgprint("""Alternatively, \
						you can also specify 'auto_email_id' in site_config.json""")
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
		self.msg_root['Date'] = email.utils.formatdate()
		if not self.reply_to: 
			self.reply_to = self.sender
		self.msg_root['Reply-To'] = self.reply_to.encode("utf-8")
		if self.cc:
			self.msg_root['CC'] = ', '.join([r.strip() for r in self.cc]).encode("utf-8")
		
	def as_string(self):
		"""validate, build message and convert to string"""
		self.validate()
		self.make()
		return self.msg_root.as_string()
		
def get_formatted_html(subject, message, footer=None):
	message = scrub_urls(message)

	return inline_css(webnotes.get_template("templates/emails/standard.html").render({
		"content": message,
		"footer": get_footer(footer),
		"title": subject
	}))

def get_footer(footer=None):
	"""append a footer (signature)"""		
	footer = footer or ""
	
	# control panel
	footer += webnotes.conn.get_value('Control Panel',None,'mail_footer') or ''
	
	# hooks
	for f in webnotes.get_hooks("mail_footer"):
		footer += webnotes.get_attr(f)
	
	footer += "<!--unsubscribe link here-->"
	
	return footer
