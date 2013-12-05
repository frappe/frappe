# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import time
import poplib
import webnotes
from webnotes.utils import extract_email_id, convert_utc_to_user_timezone, now, cint
from webnotes.utils.scheduler import log

class EmailSizeExceededError(webnotes.ValidationError): pass
class EmailTimeoutError(webnotes.ValidationError): pass
class TotalSizeExceededError(webnotes.ValidationError): pass

class IncomingMail:
	"""
		Single incoming email object. Extracts, text / html and attachments from the email
	"""
	def __init__(self, content):
		import email, email.utils
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
		
		if self.mail["Date"]:
			utc = email.utils.mktime_tz(email.utils.parsedate_tz(self.mail["Date"]))
			utc_dt = datetime.datetime.utcfromtimestamp(utc)
			self.date = convert_utc_to_user_timezone(utc_dt).strftime('%Y-%m-%d %H:%M:%S')
		else:
			self.date = now()

	def parse(self):
		for part in self.mail.walk():
			self.process_part(part)

	def set_subject(self):
		import email.header
		_subject = email.header.decode_header(self.mail.get("Subject", "No Subject"))
		self.subject = _subject[0][0] or ""
		if _subject[0][1]:
			self.subject = self.subject.decode(_subject[0][1])
		else:
			# assume that the encoding is utf-8
			self.subject = self.subject.decode("utf-8")

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
		except LookupError:
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
				# WARNING: bypass max file size exception
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
		self.settings = args or webnotes._dict()

	def check_mails(self):
		# overrride
		return True
	
	def process_message(self, mail):
		# overrride
		pass
		
	def connect(self):
		if cint(self.settings.use_ssl):
			self.pop = Timed_POP3_SSL(self.settings.host, timeout=webnotes.conf.get("pop_timeout"))
		else:
			self.pop = Timed_POP3(self.settings.host, timeout=webnotes.conf.get("pop_timeout"))
			
		self.pop.user(self.settings.username)
		self.pop.pass_(self.settings.password)
		
	def get_messages(self):
		if not self.check_mails():
			return # nothing to do
		
		webnotes.conn.commit()
		self.connect()
		
		try:
			# track if errors arised
			self.errors = False
			pop_list = self.pop.list()[1]
			num = num_copy = len(pop_list)
		
			# WARNING: Hard coded max no. of messages to be popped
			if num > 20: num = 20
			
			# size limits
			self.total_size = 0
			self.max_email_size = cint(webnotes.local.conf.get("max_email_size"))
			self.max_total_size = 5 * self.max_email_size
			
			for i, pop_meta in enumerate(pop_list):
				# do not pull more than NUM emails
				if (i+1) > num:
					break
				
				try:
					self.retrieve_message(pop_meta, i+1)
				except (TotalSizeExceededError, EmailTimeoutError):
					break
		
			# WARNING: Mark as read - message number 101 onwards from the pop list
			# This is to avoid having too many messages entering the system
			num = num_copy
			if num > 100 and not self.errors:
				for m in xrange(101, num+1):
					self.pop.dele(m)
		finally:
			# no matter the exception, pop should quit if connected
			self.pop.quit()
		
	def retrieve_message(self, pop_meta, msg_num):
		incoming_mail = None
		try:
			self.validate_pop(pop_meta)
			msg = self.pop.retr(msg_num)

			incoming_mail = IncomingMail(b'\n'.join(msg[1]))
			webnotes.conn.begin()
			self.process_message(incoming_mail)
			webnotes.conn.commit()
			
		except (TotalSizeExceededError, EmailTimeoutError):
			# propagate this error to break the loop
			raise
		
		except:
			# log performs rollback and logs error in scheduler log
			log("receive.get_messages", self.make_error_msg(msg_num, incoming_mail))
			self.errors = True
			webnotes.conn.rollback()
			
			self.pop.dele(msg_num)
		else:
			self.pop.dele(msg_num)
			
	def validate_pop(self, pop_meta):
		# throttle based on email size
		if not self.max_email_size:
			return
		
		m, size = pop_meta.split()
		size = cint(size)
		
		if size < self.max_email_size:
			self.total_size += size
			if self.total_size > self.max_total_size:
				raise TotalSizeExceededError
		else:
			raise EmailSizeExceededError
			
	def make_error_msg(self, msg_num, incoming_mail):
		error_msg = "Error in retrieving email."
		if not incoming_mail:
			try:
				# retrieve headers
				incoming_mail = IncomingMail(b'\n'.join(self.pop.top(msg_num, 5)[1]))
			except:
				pass
			
		if incoming_mail:
			error_msg += "\nDate: {date}\nFrom: {from_email}\nSubject: {subject}\n".format(
				date=incoming_mail.date, from_email=incoming_mail.from_email, subject=incoming_mail.subject)
		
		return error_msg
		
class TimerMixin(object):
	def __init__(self, *args, **kwargs):
		self.timeout = kwargs.pop('timeout', 0.0)
		self.elapsed_time = 0.0
		self._super.__init__(self, *args, **kwargs)
		if self.timeout:
			# set per operation timeout to one-fifth of total pop timeout
			self.sock.settimeout(self.timeout / 5.0)
		
	def _getline(self, *args, **kwargs):
		start_time = time.time()
		ret = self._super._getline(self, *args, **kwargs)

		self.elapsed_time += time.time() - start_time
		if self.timeout and self.elapsed_time > self.timeout:
			raise EmailTimeoutError
		
		return ret
		
	def quit(self, *args, **kwargs):
		self.elapsed_time = 0.0
		return self._super.quit(self, *args, **kwargs)
		
class Timed_POP3(TimerMixin, poplib.POP3):
	_super = poplib.POP3
		
class Timed_POP3_SSL(TimerMixin, poplib.POP3_SSL):
	_super = poplib.POP3_SSL