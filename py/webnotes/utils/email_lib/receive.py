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
			return unicode(part.get_payload(decode=True),str(charset),"ignore").encode('utf8','replace')
		except LookupError, e:
			return part.get_payload()		

	def get_attachment(self, part, charset):
		"""
			Extracts an attachment
		"""
		self.attachments.append({
			'content-type': part.get_content_type(),
			'filename': part.get_filename(),
			'content': part.get_payload(decode=True)
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

		return re.findall('(?<=\[)[\w/]+', subject)


	def process_part(self, part):
		"""
			Process a single part of an email
		"""
		charset = self.get_charset(part)
		content_type = part.get_content_type()

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
		num = len(self.pop.list()[1])
		for m in range(num):
			msg = self.pop.retr(m+1)
			try:
				self.process_message(IncomingMail('\n'.join(msg[1])))
			except:
				pass
			self.pop.dele(m+1)
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
