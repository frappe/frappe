# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import time, _socket, poplib, imaplib, email, email.utils, datetime, chardet, re, hashlib
from email_reply_parser import EmailReplyParser
from email.header import decode_header
import frappe
from frappe import _
from frappe.utils import (extract_email_id, convert_utc_to_user_timezone, now,
	cint, cstr, strip, markdown)
from frappe.utils.scheduler import log
from frappe.utils.file_manager import get_random_filename, save_file, MaxFileSizeReachedError
from email_reply_parser import EmailReplyParser
from email.header import decode_header
from frappe.utils.file_manager import get_random_filename

class EmailSizeExceededError(frappe.ValidationError): pass
class EmailTimeoutError(frappe.ValidationError): pass
class TotalSizeExceededError(frappe.ValidationError): pass
class LoginLimitExceeded(frappe.ValidationError): pass

class EmailServer:
	"""Wrapper for POP server to pull emails."""
	def __init__(self, args=None):
		self.setup(args)

	def setup(self, args=None):
		# overrride
		self.settings = args or frappe._dict()

	def check_mails(self):
		# overrride
		return True

	def process_message(self, mail):
		# overrride
		pass

	def connect(self):
		"""Connect to **Email Account**."""
		if cint(self.settings.use_imap):
			return self.connect_imap()
		else:
			return self.connect_pop()

	def connect_imap(self):
		"""Connect to IMAP"""
		try:
			if cint(self.settings.use_ssl):
				self.imap = Timed_IMAP4_SSL(self.settings.host, timeout=frappe.conf.get("pop_timeout"))
				#self.imap = imaplib.IMAP4_SSL(self.settings.host)
			else:
				self.imap = Timed_IMAP4(self.settings.host, timeout=frappe.conf.get("pop_timeout"))
			self.imap.login(self.settings.username, self.settings.password)
			# connection established!
			return True

		except _socket.error:
			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_('Invalid Mail Server. Please rectify and try again.'))
			raise

		except Exception, e:
			frappe.msgprint(_('Cannot connect: {0}').format(str(e)))
			raise

	def connect_pop(self):
		#this method return pop connection
		try:
			if cint(self.settings.use_ssl):
				self.pop = Timed_POP3_SSL(self.settings.host, timeout=frappe.conf.get("pop_timeout"))
			else:
				self.pop = Timed_POP3(self.settings.host, timeout=frappe.conf.get("pop_timeout"))

			self.pop.user(self.settings.username)
			self.pop.pass_(self.settings.password)

			# connection established!
			return True

		except _socket.error:
			# log performs rollback and logs error in Error Log
			log("receive.connect_pop")

			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_('Invalid Mail Server. Please rectify and try again.'))
			raise

		except poplib.error_proto, e:
			if self.is_temporary_system_problem(e):
				return False

			else:
				frappe.msgprint(_('Invalid User Name or Support Password. Please rectify and try again.'))
				raise

	def get_messages(self):
		"""Returns new email messages in a list."""
		if not self.check_mails():
			return # nothing to do

		frappe.db.commit()

		try:
			# track if errors arised
			self.errors = False
			self.latest_messages = []
			if cint(self.settings.use_imap):
				uid_validity = self.get_status()
			else:
				email_list = self.get_new_mails()


			# size limits
			self.total_size = 0
			self.max_email_size = cint(frappe.local.conf.get("max_email_size"))
			self.max_total_size = 5 * self.max_email_size
			if cint(self.settings.use_imap):
				#try:
				if self.check_uid_validity(uid_validity):
					email_list = self.get_new_mails()
					if email_list:
						self.get_imap_messages(email_list)
					self.sync_flags()
					self.get_seen()
					self.push_deleted()

				else:
					pass

			else:
				num = num_copy = len(email_list)

				# WARNING: Hard coded max no. of messages to be popped
				if num > 20: num = 20 #20

				for i, message_meta in enumerate(email_list):
					# do not pull more than NUM emails
					if (i+1) > num:
						break

					try:
						self.retrieve_message(message_meta, i+1)
					except (TotalSizeExceededError, EmailTimeoutError, LoginLimitExceeded):
						break

				# WARNING: Mark as read - message number 101 onwards from the pop list
				# This is to avoid having too many messages entering the system
				num = num_copy
				if not cint(self.settings.use_imap):
					if num > 100 and not self.errors:
						for m in xrange(101, num+1):
							self.pop.dele(m)

		except Exception, e:
			if self.has_login_limit_exceeded(e):
				pass

			else:
				raise

		finally:
			# no matter the exception, pop should quit if connected
			if cint(self.settings.use_imap):
				self.imap.logout()
			else:
				self.pop.quit()

		return self.latest_messages

	def get_status(self):
		passed, status = self.imap.status("Inbox", "(UIDNEXT UIDVALIDITY)")
		match = re.search(r"(?<=UIDVALIDITY )[0-9]*", status[0], re.U | re.I)
		if match:
			uid_validity = match.group(0)
		match = re.search(r"(?<=UIDNEXT )[0-9]*", status[0], re.U | re.I)
		if match:
			uidnext = match.group(0)
		frappe.db.set_value("Email Account", self.settings.email_account, "uidnext", uidnext, update_modified=False)
		self.settings.newuidnext = uidnext
		return uid_validity

	def get_new_mails(self):
		"""Return list of new mails"""
		if cint(self.settings.use_imap):
			self.imap.select("Inbox")
			if self.settings.no_remaining == '0' and self.settings.uidnext:
				if self.settings.uidnext == self.settings.newuidnext:
					return False
				else:
					response, message = self.imap.uid('search', 'UID',str(self.settings.uidnext) + ":" + self.settings.newuidnext)
			else:
				response, message = self.imap.uid('search', None, "ALL")
			email_list =  message[0].split()
		else:
			email_list = self.pop.list()[1]

		return email_list

	def check_uid_validity(self,uid_validity):
		if self.settings.uid_validity:
			if self.settings.uid_validity == uid_validity:
				return True
			else:
				#validity changed
				self.settings.no_remaining = None
				self.rebuild_uid(uid_validity)
				return True

		else:#if email account settings is blank
			uid_list = frappe.db.sql("""select uid
					from tabCommunication
					where email_account = %(email_account)s and uid is not Null
					order by uid
			""",{"email_account":self.settings.email_account},as_list=1)
			new_uid_list = []
			for i in uid_list:
				new_uid_list.append(i[0])

			if new_uid_list:#if email account
				self.rebuild_uid(uid_validity)
				return True
			else:# if no uid and no emails with uid
				frappe.db.set_value("Email Account",self.settings.email_account,"uid_validity",uid_validity)
				frappe.db.commit()
				return True

	def rebuild_uid(self,uid_validity):
		uid_list = frappe.db.sql("""select name,uid ,unique_id
	    				from `tabCommunication`
	    				where email_account = %(email_account)s and unique_id is not Null and sent_or_received = 'Received'
	    				#order by uid
	    			""", {"email_account": self.settings.email_account}, as_dict=1)

		unhandled_uid_list = frappe.db.sql("""select name,uid ,unique_id
		    				from `tabUnhandled Emails`
		    				where email_account = %(email_account)s and unique_id is not Null
		    				#order by uid
		    			""", {"email_account": self.settings.email_account}, as_dict=1)


		message_list = []
		#get message-id's to link new uid's to
		import email
		#messages = self.imap.uid('fetch', "1:*", '(BODY.PEEK[HEADER.FIELDS (FROM TO ENVELOPE-TO DATE RECEIVED)])')
		messages = self.imap.uid('fetch', "1:*", '(BODY.PEEK[HEADER])')
		for i, item in enumerate(messages[1]):
			if isinstance(item, tuple):
				# '''
				# check for uid appended to the end
				uid = re.search(r'UID [0-9]*', messages[1][i + 1], re.U | re.I)
				if uid:
					uid = uid.group()[4:]
				else:
					uid = ""

				# check for uid at start
				if not uid:
					# for m in item:
					uid = re.search(r'UID [0-9]*', messages[1][i][0], re.U | re.I)
					if uid:
						uid = uid.group()[4:]
					else:
						uid = ""
						continue
				mail = email.message_from_string(item[1])
				#unique_id = hashlib.md5((mail.get("X-Original-From") or mail["From"]) + (mail.get("To") or mail.get("Envelope-to")) + ( mail.get("Received") or mail["Date"])).hexdigest()
				unique_id = get_unique_id(mail)
				message_list.append([uid, unique_id])
		# clear out
		frappe.db.sql("""update `tabCommunication`
	    				set uid = NULL
	    			where email_account = %(email_account)s
	    			""", {"email_account": self.settings.email_account})
		frappe.db.sql("""update `tabUnhandled Emails`
			    				set uid = NULL
			    			where email_account = %(email_account)s
			    			""", {"email_account": self.settings.email_account})

		# write new uid
		new_uid = []
		for old in uid_list:
			for new in message_list:
				if old["unique_id"] == new[1]:
					frappe.db.sql("""update `tabCommunication`
	    											set uid = %(uid)s
	    										where name = %(name)s
	    										""", {"name": old["name"],
					                                  "uid": new[0]})
					break
		for old in unhandled_uid_list:
			for new in message_list:
				if old["unique_id"] == new[1]:
					frappe.db.sql("""update `tabUnhandled Emails`
			    											set uid = %(uid)s
			    										where name = %(name)s
			    										""", {"name": old["name"],
					                                          "uid": new[0]})
					break

		frappe.db.set_value("Email Account", self.settings.email_account, "uid_validity", uid_validity)
		frappe.db.set_value("Email Account", self.settings.email_account, "no_remaining", None)
		frappe.db.commit()



	def get_imap_messages(self,email_list):
		if self.settings.no_remaining == '0' and self.settings.uidnext:
			download_list = []
			for new in email_list:
				download_list.append(cint(new))
		else:
			#compare stored uid to new uid list to dl any missing messages
			uid_list = frappe.db.sql("""select uid
						from tabCommunication
						where email_account = %(email_account)s and uid is not Null
						order by uid
			""",{"email_account":self.settings.email_account},as_list=1)
			uid_list = uid_list + (frappe.db.sql("""select uid
						from `tabUnhandled Emails`
						where email_account = %(email_account)s and uid is not Null
						order by uid
			""",{"email_account":self.settings.email_account},as_list=1))
			new_uid_list = []
			for i in uid_list:
				new_uid_list.append(i[0])

			download_list = []
			for new in email_list:
				if new not in new_uid_list:
					download_list.append(cint(new))

		from itertools import count, groupby
		num = 50

		# set number of email remaining to be synced
		dl_length = len(download_list)

		lcount =1
		while len(download_list)>0:
			# trim list to specified num emails to dl at a time

			dlength = len(download_list)
			cur_download_list = download_list[dlength - num:dlength]
			if cur_download_list:
				download_list = download_list[:dlength - num]

				if lcount>=4:
					download_list = []

				# compress download list into ranges
				G=(list(x) for _,x in groupby(cur_download_list, lambda x,c=count(): next(c)-x))
				message_meta = ",".join(":".join(map(str,(g[0],g[-1])[:len(g)])) for g in G)

				messages =[]

				try:
					messages = self.imap.uid('fetch', message_meta,'(BODY.PEEK[])')

				except (TotalSizeExceededError, EmailTimeoutError), e:
					print("timeout or size exceed")
					pass
				except (imaplib.IMAP4.error),e:

					print (e)
					pass

				if messages and messages[0]=='OK':
					for i, item in enumerate(messages[1]):
						if isinstance(item, tuple):
							#check for uid appended to the end
							uid = re.search(r'UID [0-9]*', messages[1][i + 1], re.U|re.I)
							if uid:
								uid = uid.group()[4:]
							else:
								uid = ""


							#check for uid at start
							if not uid:
								#for m in item:
								uid = re.search(r'UID [0-9]*', messages[1][i][0], re.U|re.I)
								if uid:
									uid = uid.group()[4:]
								else:
									uid = ""
									continue


							if uid:
								self.latest_messages.append([item[1],uid,1])#message,uid,seen

					# set number of email remaining to be synced TEMPTEMPTEMPTEMPTEMP################################################################
					frappe.db.set_value("Email Account", self.settings.email_account, "no_remaining",dl_length-len(self.latest_messages),update_modified = False)
					frappe.db.commit()
				lcount = lcount +1

	def sync_flags(self):
		#get flags from email flag queue + join them to the matching email account and uid
		queue = frappe.db.sql("""select que.name,comm.uid,que.action,que.flag from tabCommunication as comm,`tabEmail Flag Queue` as que
			where comm.name = que.comm_name and comm.uid is not null and comm.email_account=%(email_account)s""",{"email_account":self.settings.email_account},as_dict=1)
		#loop though flags

		for item in queue:
			try:
				self.imap.uid('STORE', item.uid, item.action, item.flag)
					#delete flag matching email account
				frappe.delete_doc("Email Flag Queue",item["name"])
			except Exception,e:
				#need to do
				pass

	def get_seen(self):
		comm_list = frappe.db.sql("""select name,uid,seen from `tabCommunication`
			where email_account = %(email_account)s and uid is not null""",
		              {"email_account":self.settings.email_account},as_dict=1)

		try:
			#response, messages = self.imap.uid('fetch', '1:*', '(FLAGS)')
			response, seen_list = self.imap.uid('search', None, "SEEN")
			response, unseen_list = self.imap.uid('search', None, "UNSEEN")
		except Exception,e:
			print("failed get seen sync download")
			return
		unseen_list = unseen_list[0].split()
		for unseen in unseen_list:
			for msg in self.latest_messages:
				if unseen == msg[1]:
					msg[2] = 0

			for comm in comm_list:
				if comm.uid == unseen:
					if comm.seen:
						frappe.db.set_value('Communication', comm.name, 'seen', 0, update_modified=False)
					comm_list.remove(comm)
					break
		seen_list = seen_list[0].split()
		for seen in seen_list:
			for msg in self.latest_messages:
				if seen == msg[1]:
					msg[2] = 1

			for comm in comm_list:
				if comm.uid == seen:
					if not comm.seen:
						frappe.db.set_value('Communication', comm.name, 'seen', 1, update_modified=False)
					comm_list.remove(comm)
					break

		'''
		for item in messages:
			uid = re.search(r'UID [0-9]*', item, re.U | re.I)
			if uid:
				uid = uid.group()[4:]
			else:
				uid = ""

			# flag = re.search(r"(?<=FLAGS \()(.*?)(?=\))", item, re.U | re.I)
			flag = re.search(r"\\Seen", item, re.U | re.I)

			for msg in self.latest_messages:
				if uid == msg[1]:
					if flag:
						msg[2]=0

			for comm in comm_list:
				if comm.uid==uid:
					if flag:
						if not comm.email_seen:
							frappe.db.set_value('Communication',comm.name,'email_seen','1',update_modified=False)
					else:
						if comm.email_seen:
							frappe.db.set_value('Communication', comm.name, 'email_seen', '0', update_modified=False)
					comm_list.remove(comm)
					break
		'''
		frappe.db.commit()


	def push_deleted(self):
		pass

	def retrieve_message(self, message_meta, msg_num=None):
		incoming_mail = None
		try:
			self.validate_message_limits(message_meta)

			if cint(self.settings.use_imap):
				status, message = self.imap.uid('fetch', message_meta, '(RFC822)')
				self.latest_messages.append(message[0][1])
			else:
				msg = self.pop.retr(msg_num)
				self.latest_messages.append(b'\n'.join(msg[1]))

		except (TotalSizeExceededError, EmailTimeoutError):
			# propagate this error to break the loop
			self.errors = True
			raise

		except Exception, e:
			if self.has_login_limit_exceeded(e):
				self.errors = True
				raise LoginLimitExceeded, e

			else:
				# log performs rollback and logs error in Error Log
				log("receive.get_messages", self.make_error_msg(msg_num, incoming_mail))
				self.errors = True
				frappe.db.rollback()

				if not cint(self.settings.use_imap):
					self.pop.dele(msg_num)
				else:
					# mark as seen
					#self.imap.uid('STORE', message_meta, '+FLAGS', '(\\SEEN)')
					pass
		else:
			if not cint(self.settings.use_imap):
				self.pop.dele(msg_num)
			else:
				# mark as seen
				#self.imap.uid('STORE', message_meta, '+FLAGS', '(\\SEEN)')
				pass

	def has_login_limit_exceeded(self, e):
		return "-ERR Exceeded the login limit" in strip(cstr(e.message))

	def is_temporary_system_problem(self, e):
		messages = (
			"-ERR [SYS/TEMP] Temporary system problem. Please try again later.",
			"Connection timed out",
		)
		for message in messages:
			if message in strip(cstr(e.message)) or message in strip(cstr(getattr(e, 'strerror', ''))):
				return True
		return False

	def validate_message_limits(self, message_meta):
		# throttle based on email size
		if not self.max_email_size:
			return

		m, size = message_meta.split()
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
				incoming_mail = Email(b'\n'.join(self.pop.top(msg_num, 5)[1]))
			except:
				pass

		if incoming_mail:
			error_msg += "\nDate: {date}\nFrom: {from_email}\nSubject: {subject}\n".format(
				date=incoming_mail.date, from_email=incoming_mail.from_email, subject=incoming_mail.subject)

		return error_msg


def get_unique_id(mail):
	hash = hashlib.sha1()
	# loop though headers to make unique id looping used to resolve encoding issue of adding together
	for h in mail._headers:
		if h[0] != 'Content-Type':  # skip variable boundaries
			try:
				temp = decode_header(h[1])
				decoded = ''.join(
					[d[0].decode(d[1]).encode('ascii', 'ignore') if d[1] is not None else d[0] for d in temp])
				cleaned = re.sub(r"\s+", u"", decoded,
				                 flags=re.UNICODE)  # gmail fix as returns different whitespace if download only headers
				hash.update(cleaned)
			except:
				pass
	return hash.hexdigest()

class Email:
	"""Wrapper for an email."""
	def __init__(self, content):
		"""Parses headers, content, attachments from given raw message.

		:param content: Raw message."""
		self.raw = content
		self.mail = email.message_from_string(self.raw)

		self.text_content = ''
		self.html_content = ''
		self.attachments = []
		self.cid_map = {}
		self.parse()
		self.set_content_and_type()
		self.set_subject()
		self.set_from()
		self.message_id = self.mail.__getitem__('Message-ID')
		#self.unique_id = hashlib.md5((self.mail.get("X-Original-From") or self.mail["From"])+(self.mail.get("To") or self.mail.get("Envelope-to"))+(self.mail.get("Received") or self.mail["Date"] )).hexdigest()



		self.unique_id = get_unique_id(self.mail)

		# gmail mailing-list compatibility
		# use X-Original-Sender if available, as gmail sometimes modifies the 'From'
		# _from_email = self.mail.get("X-Original-From") or self.mail["From"]
		# 
		# self.from_email = extract_email_id(_from_email)
		# if self.from_email:
		# 	self.from_email = self.from_email.lower()
		# 
		# #self.from_real_name = email.utils.parseaddr(_from_email)[0]
		# 
		# _from_real_name = decode_header(email.utils.parseaddr(_from_email)[0])
		# self.from_real_name = decode_header(email.utils.parseaddr(_from_email)[0])[0][0] or ""
		# 
		# try:
		# 	if _from_real_name[0][1]:
		# 		self.from_real_name = self.from_real_name.decode(_from_real_name[0][1])
		# 	else:
		# 		# assume that the encoding is utf-8
		# 		self.from_real_name = self.from_real_name.decode("utf-8")
		# except UnicodeDecodeError,e:
		# 	print e
		# 	pass

		#self.from_real_name = email.Header.decode_header(email.utils.parseaddr(_from_email)[0])[0][0]
		self.To = self.mail.get("To")
		if self.To:
			self.To = self.To.lower()
		self.CC = self.mail.get("CC")
		if self.CC:
			self.CC = self.CC.lower()
		if self.mail["Date"]:
			utc = email.utils.mktime_tz(email.utils.parsedate_tz(self.mail["Date"]))
			utc_dt = datetime.datetime.utcfromtimestamp(utc)
			self.date = convert_utc_to_user_timezone(utc_dt).strftime('%Y-%m-%d %H:%M:%S')
		else:
			self.date = now()

	def parse(self):
		"""Walk and process multi-part email."""
		for part in self.mail.walk():
			self.process_part(part)

	def set_subject(self):
		"""Parse and decode `Subject` header."""
		_subject = decode_header(self.mail.get("Subject", "No Subject"))
		self.subject = _subject[0][0] or ""
		try:
			if _subject[0][1]:
				self.subject = self.subject.decode(_subject[0][1])
			else:
				# assume that the encoding is utf-8
				self.subject = self.subject.decode("utf-8")[:140]
		except UnicodeDecodeError:
			#try:
			#	self.subject = self.subject.decode("gb18030")
			#except UnicodeDecodeError:
			self.subject = u'Error Decoding Subject'
		#if self.subject and len(self.subject)>140:
		#	self.subject = self.subject[:135]
		import re

		emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           "]+", flags=re.UNICODE)
		self.subject = emoji_pattern.sub(r'', self.subject)

		if not self.subject:
			self.subject = "No Subject"

	def set_from(self):
		# gmail mailing-list compatibility
		# use X-Original-Sender if available, as gmail sometimes modifies the 'From'
		_from_email = self.mail.get("X-Original-From") or self.mail["From"]
		_from_email, encoding = decode_header(_from_email)[0]
		_reply_to = self.mail.get("Reply-To")

		if encoding:
			_from_email = _from_email.decode(encoding)
		else:
			_from_email = _from_email.decode('utf-8')

		if _reply_to and not frappe.db.get_value('Email Account', {"email_id":_reply_to}, 'email_id'):
			self.from_email = _reply_to
		else:
			self.from_email = extract_email_id(_from_email)
			
		if self.from_email:
			self.from_email = self.from_email.lower()
			
		self.from_real_name = email.utils.parseaddr(_from_email)[0]

	def set_content_and_type(self):
		self.content, self.content_type = '[Blank Email]', 'text/plain'
		if self.html_content:
			self.content, self.content_type = self.html_content, 'text/html'
		else:
			self.content, self.content_type = EmailReplyParser.parse_reply(self.text_content), 'text/plain'

	def process_part(self, part):
		"""Parse email `part` and set it to `text_content`, `html_content` or `attachments`."""
		content_type = part.get_content_type()
		if content_type == 'text/plain':
			self.text_content += self.get_payload(part)

		elif content_type == 'text/html':
			self.html_content += self.get_payload(part)

		elif content_type == 'message/rfc822':
			# sent by outlook when another email is sent as an attachment to this email
			self.show_attached_email_headers_in_content(part)

		elif part.get_filename():
			self.get_attachment(part)

	def show_attached_email_headers_in_content(self, part):
		# get the multipart/alternative message
		message = list(part.walk())[1]
		headers = []
		for key in ('From', 'To', 'Subject', 'Date'):
			value = cstr(message.get(key))
			if value:
				headers.append('{label}: {value}'.format(label=_(key), value=value))

		self.text_content += '\n'.join(headers)
		self.html_content += '<hr>' + '\n'.join('<p>{0}</p>'.format(h) for h in headers)

		if not message.is_multipart() and message.get_content_type()=='text/plain':
			# email.parser didn't parse it!
			text_content = self.get_payload(message)
			self.text_content += text_content
			self.html_content += markdown(text_content)

	def get_charset(self, part):
		"""Detect chartset."""
		charset = part.get_content_charset()
		if not charset:
			charset = chardet.detect(str(part))['encoding']

		return charset

	def get_payload(self, part):
		charset = self.get_charset(part)

		try:
			return unicode(part.get_payload(decode=True), str(charset), "ignore")
		except LookupError:
			return part.get_payload()

	def get_attachment(self, part):
		#charset = self.get_charset(part)
		fcontent = part.get_payload(decode=True)

		if fcontent:
			content_type = part.get_content_type()
			fname = part.get_filename()
			if fname:
				try:
					fname = cstr(decode_header(fname)[0][0])
				except:
					fname = get_random_filename(content_type=content_type)
			else:
				fname = get_random_filename(content_type=content_type)

			self.attachments.append({
				'content_type': content_type,
				'fname': fname,
				'fcontent': fcontent,
			})

			cid = (part.get("Content-Id") or "").strip("><")
			if cid:
				self.cid_map[fname] = cid

	def save_attachments_in_doc(self, doc):
		"""Save email attachments in given document."""
		saved_attachments = []

		for attachment in self.attachments:
			try:
				file_data = save_file(attachment['fname'], attachment['fcontent'],
					doc.doctype, doc.name, is_private=1)
				saved_attachments.append(file_data)

				if attachment['fname'] in self.cid_map:
					self.cid_map[file_data.name] = self.cid_map[attachment['fname']]

			except MaxFileSizeReachedError:
				# WARNING: bypass max file size exception
				pass
			except frappe.DuplicateEntryError:
				# same file attached twice??
				pass

		return saved_attachments

	def get_thread_id(self):
		"""Extract thread ID from `[]`"""
		l = re.findall('(?<=\[)[\w/-]+', self.subject)
		return l and l[0] or None


# fix due to a python bug in poplib that limits it to 2048
poplib._MAXLINE = 20480

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
class Timed_IMAP4(TimerMixin, imaplib.IMAP4):
	_super = imaplib.IMAP4

class Timed_IMAP4_SSL(TimerMixin, imaplib.IMAP4_SSL):
	_super = imaplib.IMAP4_SSL
