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
	This module contains classes for managing incoming emails
"""

class IncomingMail:
	"""
		Single incoming email object. Extracts, text / html and attachments from the email
	"""
	def __init__(self, content):
		"""
			Parse the incoming mail content
		"""
		import email
		
		self.mail = email.message_from_string(content)
		
		self.text_content = ''
		self.html_content = ''
		self.attachments = []
		self.parse()

	def get_text_content(self):
		"""
			Returns the text parts of the email. If None, then HTML parts
		"""
		return self.text_content or self.html_content

	def get_charset(self, part):
		"""
			Guesses character set
		"""
		charset = part.get_content_charset()
		if not charset:
			import chardet
			charset = chardet.detect(str(part))['encoding']

		return charset
			
	def get_payload(self, part, charset):
		"""
			get utf-8 encoded part content
		"""
		try:
			return unicode(part.get_payload(decode=True),str(charset),"ignore")
		except LookupError, e:
			return part.get_payload()		

	def get_attachment(self, part, charset):
		"""
			Extracts an attachment
		"""
		self.attachments.append({
			'content-type': part.get_content_type(),
			'filename': part.get_filename(),
			'content': part.get_payload(decode=True),
		})
				
	def parse(self):
		"""
			Extracts text, html and attachments from the mail
		"""
		for part in self.mail.walk():
			self.process_part(part)

	def get_thread_id(self):
		"""
			Extracts thread id of the message between first [] 
			from the subject
		"""
		import re
		subject = self.mail.get('Subject', '')

		return re.findall('(?<=\[)[\w/-]+', subject)


	def process_part(self, part):
		"""
			Process a single part of an email
		"""
		content_type = part.get_content_type()
		charset = part.get_content_charset()
		if not charset: charset = self.get_charset(part)

		if content_type == 'text/plain':
			self.text_content += self.get_payload(part, charset)

		if content_type == 'text/html':
			self.html_content += self.get_payload(part, charset)

		if part.get_filename():
			self.get_attachment(part, charset)

class POP3Mailbox:
	"""
		A simple pop3 mailbox, abstracts connection and mail extraction
		To use, subclass it and override method process_message(from, subject, text, thread_id)
	"""
	
	def __init__(self, settings_doc):
		"""
			settings_doc must contain
			use_ssl, host, username, password
			(by name or object)
		"""
		if isinstance(settings_doc, basestring):
			from webnotes.model.doc import Document
			self.settings = Document(settings_doc, settings_doc)
		else:
			self.settings = settings_doc

	def connect(self):
		"""
			Connects to the mailbox
		"""
		import poplib
		
		if self.settings.use_ssl:
			self.pop = poplib.POP3_SSL(self.settings.host)
		else:
			self.pop = poplib.POP3(self.settings.host)
		self.pop.user(self.settings.username)
		self.pop.pass_(self.settings.password)
		
	
	def get_messages(self):
		"""
			Loads messages from the mailbox and calls
			process_message for each message
		"""
		
		if not self.check_mails():
			return # nothing to do
		
		self.connect()
		num = num_copy = len(self.pop.list()[1])

		# WARNING: Hard coded max no. of messages to be popped
		if num > 20: num = 20
		for m in xrange(1, num+1):
			msg = self.pop.retr(m)
			
			try:
				self.process_message(IncomingMail(b'\n'.join(msg[1])))
			except Exception, e:
				pass
				# import webnotes
				# webnotes.errprint(e)

			self.pop.dele(m)
		
		# WARNING: Delete message number 101 onwards from the pop list
		# This is to avoid having too many messages entering the system
		num = num_copy
		if num > 100:
			for m in xrange(101, num+1):
				self.pop.dele(m)
		
		self.pop.quit()
		
	def check_mails(self):
		"""
			To be overridden
			If mailbox is to be scanned, returns true
		"""
		return True
	
	def process_message(self, mail):
		"""
			To be overriden
		"""
		pass
