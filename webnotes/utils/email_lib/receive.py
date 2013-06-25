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
import webnotes
from webnotes.utils import extract_email_id, convert_utc_to_user_timezone

class IncomingMail:
	"""
		Single incoming email object. Extracts, text / html and attachments from the email
	"""
	def __init__(self, content):
		import email, email.utils, email.header
		import datetime
		
		self.mail = email.message_from_string(content)
		
		self.text_content = ''
		self.html_content = ''
		self.attachments = []	
		self.parse()
		self.set_content_and_type()
		self.set_subject()

		self.from_email = extract_email_id(self.mail["From"])
		self.from_real_name = email.utils.parseaddr(self.mail["From"])[0]
		
		utc = email.utils.mktime_tz(email.utils.parsedate_tz(self.mail["Date"]))
		utc_dt = datetime.datetime.utcfromtimestamp(utc)
		self.date = convert_utc_to_user_timezone(utc_dt).strftime('%Y-%m-%d %H:%M:%S')

	def parse(self):
		for part in self.mail.walk():
			self.process_part(part)

	def set_subject(self):
		_subject = email.header.decode_header(self.mail.get("Subject", "No Subject"))
		self.subject = _subject[0][0]
		if _subject[0][1]:
			self.subject = _subject[0][0].decode(_subject[0][1])

	def set_content_and_type(self):
		self.content, self.content_type = '[Blank Email]', 'text/plain'
		if self.text_content:
			self.content, self.content_type = self.text_content, 'text/plain'
		else:
			self.content, self.content_type = self.html_content, 'text/html'
		
	def process_part(self, part):
		content_type = part.get_content_type()
		charset = part.get_content_charset()
		if not charset: charset = self.get_charset(part)

		if content_type == 'text/plain':
			self.text_content += self.get_payload(part, charset)

		if content_type == 'text/html':
			self.html_content += self.get_payload(part, charset)

		if part.get_filename():
			self.get_attachment(part, charset)

	def get_text_content(self):
		return self.text_content or self.html_content

	def get_charset(self, part):
		charset = part.get_content_charset()
		if not charset:
			import chardet
			charset = chardet.detect(str(part))['encoding']

		return charset
			
	def get_payload(self, part, charset):
		try:
			return unicode(part.get_payload(decode=True),str(charset),"ignore")
		except LookupError, e:
			return part.get_payload()		

	def get_attachment(self, part, charset):
		self.attachments.append({
			'content-type': part.get_content_type(),
			'filename': part.get_filename(),
			'content': part.get_payload(decode=True),
		})
	
	def save_attachments_in_doc(self, doc):
		from webnotes.utils.file_manager import save_file, MaxFileSizeReachedError
		for attachment in self.attachments:
			try:
				fid = save_file(attachment['filename'], attachment['content'], 
					doc.doctype, doc.name)
			except MaxFileSizeReachedError:
				# bypass max file size exception
				pass
			except webnotes.DuplicateEntryError:
				# same file attached twice??
				pass

	def get_thread_id(self):
		import re
		l = re.findall('(?<=\[)[\w/-]+', self.subject)
		return l and l[0] or None

class POP3Mailbox:
	def __init__(self, args=None):
		self.setup(args)
		self.get_messages()
	
	def setup(self, args=None):
		# overrride
		import webnotes
		self.settings = args or webnotes._dict()

	def check_mails(self):
		# overrride
		return True
	
	def process_message(self, mail):
		# overrride
		pass
		
	def connect(self):
		import poplib
		
		if self.settings.use_ssl:
			self.pop = poplib.POP3_SSL(self.settings.host)
		else:
			self.pop = poplib.POP3(self.settings.host)
		self.pop.user(self.settings.username)
		self.pop.pass_(self.settings.password)
	
	def get_messages(self):
		import webnotes
		
		if not self.check_mails():
			return # nothing to do
		
		webnotes.conn.commit()

		self.connect()
		num = num_copy = len(self.pop.list()[1])
		
		# track if errors arised
		errors = False
		
		# WARNING: Hard coded max no. of messages to be popped
		if num > 20: num = 20
		for m in xrange(1, num+1):
			msg = self.pop.retr(m)
			# added back dele, as most pop3 servers seem to require msg to be deleted
			# else it will again be fetched in self.pop.list()
			self.pop.dele(m)
			
			try:
				incoming_mail = IncomingMail(b'\n'.join(msg[1]))
				webnotes.conn.begin()
				self.process_message(incoming_mail)
				webnotes.conn.commit()
			except:
				from webnotes.utils.scheduler import log
				# log performs rollback and logs error in scheduler log
				log("receive.get_messages")
				errors = True
				webnotes.conn.rollback()
		
		# WARNING: Mark as read - message number 101 onwards from the pop list
		# This is to avoid having too many messages entering the system
		num = num_copy
		if num > 100 and not errors:
			for m in xrange(101, num+1):
				self.pop.dele(m)
		
		self.pop.quit()
		webnotes.conn.begin()
		
