# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import datetime
import email
import email.utils
import imaplib
import poplib
import re
import time
from email.header import decode_header

import _socket
import chardet
import six
from email_reply_parser import EmailReplyParser

import frappe
from frappe import _, safe_decode, safe_encode
from frappe.core.doctype.file.file import MaxFileSizeReachedError, get_random_filename
from frappe.utils import (
	cint,
	convert_utc_to_user_timezone,
	cstr,
	extract_email_id,
	get_string_between,
	markdown,
	now,
	parse_addr,
	strip,
)

# fix due to a python bug in poplib that limits it to 2048
poplib._MAXLINE = 20480


class EmailSizeExceededError(frappe.ValidationError):
	pass


class EmailTimeoutError(frappe.ValidationError):
	pass


class TotalSizeExceededError(frappe.ValidationError):
	pass


class LoginLimitExceeded(frappe.ValidationError):
	pass


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
				self.imap = Timed_IMAP4_SSL(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.get("pop_timeout")
				)
			else:
				self.imap = Timed_IMAP4(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.get("pop_timeout")
				)
				if self.settings.use_starttls:
					self.imap.starttls()

			self.imap.login(self.settings.username, self.settings.password)
			# connection established!
			return True

		except _socket.error:
			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_("Invalid Mail Server. Please rectify and try again."))
			raise

	def connect_pop(self):
		# this method return pop connection
		try:
			if cint(self.settings.use_ssl):
				self.pop = Timed_POP3_SSL(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.get("pop_timeout")
				)
			else:
				self.pop = Timed_POP3(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.get("pop_timeout")
				)

			self.pop.user(self.settings.username)
			self.pop.pass_(self.settings.password)

			# connection established!
			return True

		except _socket.error:
			# log performs rollback and logs error in Error Log
			frappe.log_error("receive.connect_pop")

			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_("Invalid Mail Server. Please rectify and try again."))
			raise

		except poplib.error_proto as e:
			if self.is_temporary_system_problem(e):
				return False

			else:
				frappe.msgprint(_("Invalid User Name or Support Password. Please rectify and try again."))
				raise

	def get_messages(self):
		"""Returns new email messages in a list."""
		if not self.check_mails():
			return  # nothing to do

		frappe.db.commit()

		if not self.connect():
			return

		uid_list = []

		try:
			# track if errors arised
			self.errors = False
			self.latest_messages = []
			self.seen_status = {}
			self.uid_reindexed = False

			uid_list = email_list = self.get_new_mails()

			if not email_list:
				return

			num = num_copy = len(email_list)

			# WARNING: Hard coded max no. of messages to be popped
			if num > 50:
				num = 50

			# size limits
			self.total_size = 0
			self.max_email_size = cint(frappe.local.conf.get("max_email_size"))
			self.max_total_size = 5 * self.max_email_size

			for i, message_meta in enumerate(email_list):
				# do not pull more than NUM emails
				if (i + 1) > num:
					break

				try:
					self.retrieve_message(message_meta, i + 1)
				except (TotalSizeExceededError, EmailTimeoutError, LoginLimitExceeded):
					break
			# WARNING: Mark as read - message number 101 onwards from the pop list
			# This is to avoid having too many messages entering the system
			num = num_copy
			if not cint(self.settings.use_imap):
				if num > 100 and not self.errors:
					for m in range(101, num + 1):
						self.pop.dele(m)

		except Exception as e:
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

		out = {"latest_messages": self.latest_messages}
		if self.settings.use_imap:
			out.update(
				{"uid_list": uid_list, "seen_status": self.seen_status, "uid_reindexed": self.uid_reindexed}
			)

		return out

	def get_new_mails(self):
		"""Return list of new mails"""
		if cint(self.settings.use_imap):
			email_list = []
			self.check_imap_uidvalidity()

			readonly = False if self.settings.email_sync_rule == "UNSEEN" else True

			self.imap.select("Inbox", readonly=readonly)
			response, message = self.imap.uid("search", None, self.settings.email_sync_rule)
			if message[0]:
				email_list = message[0].split()
		else:
			email_list = self.pop.list()[1]

		return email_list

	def check_imap_uidvalidity(self):
		# compare the UIDVALIDITY of email account and imap server
		uid_validity = self.settings.uid_validity

		response, message = self.imap.status("Inbox", "(UIDVALIDITY UIDNEXT)")
		current_uid_validity = self.parse_imap_response("UIDVALIDITY", message[0]) or 0

		uidnext = int(self.parse_imap_response("UIDNEXT", message[0]) or "1")
		frappe.db.set_value("Email Account", self.settings.email_account, "uidnext", uidnext)

		if not uid_validity or uid_validity != current_uid_validity:
			# uidvalidity changed & all email uids are reindexed by server
			frappe.db.sql(
				"""update `tabCommunication` set uid=-1 where communication_medium='Email'
				and email_account=%s""",
				(self.settings.email_account,),
			)
			frappe.db.sql(
				"""update `tabEmail Account` set uidvalidity=%s, uidnext=%s where
				name=%s""",
				(current_uid_validity, uidnext, self.settings.email_account),
			)

			# uid validity not found pulling emails for first time
			if not uid_validity:
				self.settings.email_sync_rule = "UNSEEN"
				return

			sync_count = 100 if uid_validity else int(self.settings.initial_sync_count)
			from_uid = (
				1 if uidnext < (sync_count + 1) or (uidnext - sync_count) < 1 else uidnext - sync_count
			)
			# sync last 100 email
			self.settings.email_sync_rule = "UID {}:{}".format(from_uid, uidnext)
			self.uid_reindexed = True

		elif uid_validity == current_uid_validity:
			return

	def parse_imap_response(self, cmd, response):
		pattern = r"(?<={cmd} )[0-9]*".format(cmd=cmd)
		match = re.search(pattern, response.decode("utf-8"), re.U | re.I)
		if match:
			return match.group(0)
		else:
			return None

	def retrieve_message(self, message_meta, msg_num=None):
		incoming_mail = None
		try:
			self.validate_message_limits(message_meta)

			if cint(self.settings.use_imap):
				status, message = self.imap.uid("fetch", message_meta, "(BODY.PEEK[] BODY.PEEK[HEADER] FLAGS)")
				raw = message[0]

				self.get_email_seen_status(message_meta, raw[0])
				self.latest_messages.append(raw[1])
			else:
				msg = self.pop.retr(msg_num)
				self.latest_messages.append(b"\n".join(msg[1]))
		except (TotalSizeExceededError, EmailTimeoutError):
			# propagate this error to break the loop
			self.errors = True
			raise

		except Exception as e:
			if self.has_login_limit_exceeded(e):
				self.errors = True
				raise LoginLimitExceeded(e)

			else:
				# log performs rollback and logs error in Error Log
				frappe.log_error("receive.get_messages", self.make_error_msg(msg_num, incoming_mail))
				self.errors = True
				frappe.db.rollback()

				if not cint(self.settings.use_imap):
					self.pop.dele(msg_num)
				else:
					# mark as seen if email sync rule is UNSEEN (syncing only unseen mails)
					if self.settings.email_sync_rule == "UNSEEN":
						self.imap.uid("STORE", message_meta, "+FLAGS", "(\\SEEN)")
		else:
			if not cint(self.settings.use_imap):
				self.pop.dele(msg_num)
			else:
				# mark as seen if email sync rule is UNSEEN (syncing only unseen mails)
				if self.settings.email_sync_rule == "UNSEEN":
					self.imap.uid("STORE", message_meta, "+FLAGS", "(\\SEEN)")

	def get_email_seen_status(self, uid, flag_string):
		"""parse the email FLAGS response"""
		if not flag_string:
			return None

		flags = []
		for flag in imaplib.ParseFlags(flag_string) or []:
			pattern = re.compile(r"\w+")
			match = re.search(pattern, frappe.as_unicode(flag))
			flags.append(match.group(0))

		if "Seen" in flags:
			self.seen_status.update({uid: "SEEN"})
		else:
			self.seen_status.update({uid: "UNSEEN"})

	def has_login_limit_exceeded(self, e):
		return "-ERR Exceeded the login limit" in strip(cstr(e.message))

	def is_temporary_system_problem(self, e):
		messages = (
			"-ERR [SYS/TEMP] Temporary system problem. Please try again later.",
			"Connection timed out",
		)
		for message in messages:
			if message in strip(cstr(e)) or message in strip(cstr(getattr(e, "strerror", ""))):
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
				incoming_mail = Email(b"\n".join(self.pop.top(msg_num, 5)[1]))
			except Exception:
				pass

		if incoming_mail:
			error_msg += "\nDate: {date}\nFrom: {from_email}\nSubject: {subject}\n".format(
				date=incoming_mail.date, from_email=incoming_mail.from_email, subject=incoming_mail.subject
			)

		return error_msg

	def update_flag(self, uid_list=None):
		"""set all uids mails the flag as seen"""

		if not uid_list:
			return

		if not self.connect():
			return

		self.imap.select("Inbox")
		for uid, operation in uid_list.items():
			if not uid:
				continue

			op = "+FLAGS" if operation == "Read" else "-FLAGS"
			try:
				self.imap.uid("STORE", uid, op, "(\\SEEN)")
			except Exception:
				continue


class Email:
	"""Wrapper for an email."""

	def __init__(self, content):
		"""Parses headers, content, attachments from given raw message.

		:param content: Raw message."""
		if six.PY2:
			self.mail = email.message_from_string(safe_encode(content))
		else:
			if isinstance(content, bytes):
				self.mail = email.message_from_bytes(content)
			else:
				self.mail = email.message_from_string(content)

		self.text_content = ""
		self.html_content = ""
		self.attachments = []
		self.cid_map = {}
		self.parse()
		self.set_content_and_type()
		self.set_subject()
		self.set_from()

		message_id = self.mail.get("Message-ID") or ""
		self.message_id = get_string_between("<", message_id, ">")

		if self.mail["Date"]:
			try:
				utc = email.utils.mktime_tz(email.utils.parsedate_tz(self.mail["Date"]))
				utc_dt = datetime.datetime.utcfromtimestamp(utc)
				self.date = convert_utc_to_user_timezone(utc_dt).strftime("%Y-%m-%d %H:%M:%S")
			except Exception:
				self.date = now()
		else:
			self.date = now()
		if self.date > now():
			self.date = now()

	def parse(self):
		"""Walk and process multi-part email."""
		for part in self.mail.walk():
			self.process_part(part)

	def set_subject(self):
		"""Parse and decode `Subject` header."""
		_subject = decode_header(self.mail.get("Subject", "No Subject"))
		self.subject = _subject[0][0] or ""
		if _subject[0][1]:
			self.subject = safe_decode(self.subject, _subject[0][1])
		else:
			# assume that the encoding is utf-8
			self.subject = safe_decode(self.subject)[:140]

		if not self.subject:
			self.subject = "No Subject"

	def set_from(self):
		# gmail mailing-list compatibility
		# use X-Original-Sender if available, as gmail sometimes modifies the 'From'
		_from_email = self.decode_email(self.mail.get("X-Original-From") or self.mail["From"])
		_reply_to = self.decode_email(self.mail.get("Reply-To"))

		if _reply_to and not frappe.db.get_value("Email Account", {"email_id": _reply_to}, "email_id"):
			self.from_email = extract_email_id(_reply_to)
		else:
			self.from_email = extract_email_id(_from_email)

		if self.from_email:
			self.from_email = self.from_email.lower()

		self.from_real_name = parse_addr(_from_email)[0] if "@" in _from_email else _from_email

	def decode_email(self, email):
		if not email:
			return
		decoded = ""
		for part, encoding in decode_header(
			frappe.as_unicode(email).replace('"', " ").replace("'", " ")
		):
			if encoding:
				decoded += part.decode(encoding)
			else:
				decoded += safe_decode(part)
		return decoded

	def set_content_and_type(self):
		self.content, self.content_type = "[Blank Email]", "text/plain"
		if self.html_content:
			self.content, self.content_type = self.html_content, "text/html"
		else:
			self.content, self.content_type = (
				EmailReplyParser.read(self.text_content).text.replace("\n", "\n\n"),
				"text/plain",
			)

	def process_part(self, part):
		"""Parse email `part` and set it to `text_content`, `html_content` or `attachments`."""
		content_type = part.get_content_type()
		if content_type == "text/plain":
			self.text_content += self.get_payload(part)

		elif content_type == "text/html":
			self.html_content += self.get_payload(part)

		elif content_type == "message/rfc822":
			# sent by outlook when another email is sent as an attachment to this email
			self.show_attached_email_headers_in_content(part)

		elif part.get_filename() or "image" in content_type:
			self.get_attachment(part)

	def show_attached_email_headers_in_content(self, part):
		# get the multipart/alternative message
		try:
			from html import escape  # python 3.x
		except ImportError:
			from cgi import escape  # python 2.x

		message = list(part.walk())[1]
		headers = []
		for key in ("From", "To", "Subject", "Date"):
			value = cstr(message.get(key))
			if value:
				headers.append("{label}: {value}".format(label=_(key), value=escape(value)))

		self.text_content += "\n".join(headers)
		self.html_content += "<hr>" + "\n".join("<p>{0}</p>".format(h) for h in headers)

		if not message.is_multipart() and message.get_content_type() == "text/plain":
			# email.parser didn't parse it!
			text_content = self.get_payload(message)
			self.text_content += text_content
			self.html_content += markdown(text_content)

	def get_charset(self, part):
		"""Detect charset."""
		charset = part.get_content_charset()
		if not charset:
			charset = chardet.detect(safe_encode(cstr(part)))["encoding"]

		return charset

	def get_payload(self, part):
		charset = self.get_charset(part)

		try:
			return str(part.get_payload(decode=True), str(charset), "ignore")
		except LookupError:
			return part.get_payload()

	def get_attachment(self, part):
		# charset = self.get_charset(part)
		fcontent = part.get_payload(decode=True)

		if fcontent:
			content_type = part.get_content_type()
			fname = part.get_filename()
			if fname:
				try:
					fname = fname.replace("\n", " ").replace("\r", "")
					fname = cstr(decode_header(fname)[0][0])
				except Exception:
					fname = get_random_filename(content_type=content_type)
			else:
				fname = get_random_filename(content_type=content_type)

			self.attachments.append(
				{
					"content_type": content_type,
					"fname": fname,
					"fcontent": fcontent,
				}
			)

			cid = (cstr(part.get("Content-Id")) or "").strip("><")
			if cid:
				self.cid_map[fname] = cid

	def save_attachments_in_doc(self, doc):
		"""Save email attachments in given document."""
		saved_attachments = []

		for attachment in self.attachments:
			try:
				_file = frappe.get_doc(
					{
						"doctype": "File",
						"file_name": attachment["fname"],
						"attached_to_doctype": doc.doctype,
						"attached_to_name": doc.name,
						"is_private": 1,
						"content": attachment["fcontent"],
					}
				)
				_file.save()
				saved_attachments.append(_file)

				if attachment["fname"] in self.cid_map:
					self.cid_map[_file.name] = self.cid_map[attachment["fname"]]

			except MaxFileSizeReachedError:
				# WARNING: bypass max file size exception
				pass
			except frappe.FileAlreadyAttachedException:
				pass
			except frappe.DuplicateEntryError:
				# same file attached twice??
				pass

		return saved_attachments

	def get_thread_id(self):
		"""Extract thread ID from `[]`"""
		l = re.findall(r"(?<=\[)[\w/-]+", self.subject)
		return l and l[0] or None


# fix due to a python bug in poplib that limits it to 2048
poplib._MAXLINE = 20480
imaplib._MAXLINE = 20480


class TimerMixin(object):
	def __init__(self, *args, **kwargs):
		self.timeout = kwargs.pop("timeout", 0.0)
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
