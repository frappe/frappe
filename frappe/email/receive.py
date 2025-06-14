# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import _socket
import datetime
import email
import email.utils
import imaplib
import json
import poplib
import re
import ssl
from contextlib import suppress
from email.errors import HeaderParseError
from email.header import decode_header
from urllib.parse import unquote

import chardet
from email_reply_parser import EmailReplyParser

import frappe
from frappe import _, safe_decode, safe_encode
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.core.doctype.file.utils import get_random_filename
from frappe.email.oauth import Oauth
from frappe.utils import (
	add_days,
	cint,
	convert_utc_to_system_timezone,
	cstr,
	extract_email_id,
	get_datetime,
	get_string_between,
	markdown,
	now,
	parse_addr,
	sanitize_html,
	strip,
)
from frappe.utils.html_utils import clean_email_html
from frappe.utils.user import is_system_user

# fix due to a python bug in poplib that limits it to 2048
poplib._MAXLINE = 1_00_000

THREAD_ID_PATTERN = re.compile(r"(?<=\[)[\w/-]+")
WORDS_PATTERN = re.compile(r"\w+")

ALTERNATE_CHARSET_MAP = {
	"windows-874": "cp874",
}


class EmailSizeExceededError(frappe.ValidationError):
	pass


class LoginLimitExceeded(frappe.ValidationError):
	pass


class SentEmailInInboxError(Exception):
	pass


class EmailServer:
	"""Wrapper for POP server to pull emails."""

	def __init__(self, args=None):
		self.retry_limit = 3
		self.retry_count = 0
		self.settings = args or frappe._dict()

	def connect(self):
		"""Connect to **Email Account**."""
		return self.connect_imap() if cint(self.settings.use_imap) else self.connect_pop()

	def connect_imap(self):
		"""Connect to IMAP"""
		try:
			if cint(self.settings.use_ssl):
				self.imap = imaplib.IMAP4_SSL(
					self.settings.host,
					self.settings.incoming_port,
					timeout=frappe.conf.pop_timeout,
					ssl_context=ssl.create_default_context(),
				)
			else:
				self.imap = imaplib.IMAP4(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.pop_timeout
				)

				if cint(self.settings.use_starttls):
					self.imap.starttls()

			if self.settings.use_oauth:
				Oauth(
					self.imap,
					self.settings.email_account,
					self.settings.username,
					self.settings.access_token,
				).connect()

			else:
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
				self.pop = poplib.POP3_SSL(
					self.settings.host,
					self.settings.incoming_port,
					timeout=frappe.conf.pop_timeout,
					context=ssl.create_default_context(),
				)
			else:
				self.pop = poplib.POP3(
					self.settings.host, self.settings.incoming_port, timeout=frappe.conf.pop_timeout
				)

			if self.settings.use_oauth:
				Oauth(
					self.pop,
					self.settings.email_account,
					self.settings.username,
					self.settings.access_token,
				).connect()

			else:
				self.pop.user(self.settings.username)
				self.pop.pass_(self.settings.password)

			# connection established!
			return True

		except _socket.error:
			frappe.log_error("POP: Unable to connect")

			# Invalid mail server -- due to refusing connection
			frappe.msgprint(_("Invalid Mail Server. Please rectify and try again."))
			raise

		except poplib.error_proto as e:
			if self.is_temporary_system_problem(e):
				return False

			else:
				frappe.msgprint(_("Invalid User Name or Support Password. Please rectify and try again."))
				raise

	def select_imap_folder(self, folder):
		res = self.imap.select(f'"{folder}"')
		return res[0] == "OK"  # The folder exists TODO: handle other responses too

	def logout(self):
		if cint(self.settings.use_imap):
			self.imap.logout()
		else:
			self.pop.quit()
		return

	def get_messages(self, folder="INBOX"):
		"""Return new email messages."""

		self.latest_messages = []
		self.seen_status = {}
		self.uid_reindexed = False

		email_list = self.get_new_mails(folder)

		for i, uid in enumerate(email_list[:100]):
			try:
				self.retrieve_message(uid, i + 1, folder)
			except (_socket.timeout, LoginLimitExceeded):
				# get whatever messages were retrieved
				break

		out = {"latest_messages": self.latest_messages}
		if self.settings.use_imap:
			out.update(
				{"uid_list": email_list, "seen_status": self.seen_status, "uid_reindexed": self.uid_reindexed}
			)

		return out

	def get_new_mails(self, folder):
		"""Return list of new mails"""
		email_list = []
		if cint(self.settings.use_imap):
			self.check_imap_uidvalidity(folder)

			readonly = self.settings.email_sync_rule != "UNSEEN"

			self.imap.select(folder, readonly=readonly)
			response, message = self.imap.uid("search", None, self.settings.email_sync_rule)
			if message[0]:
				email_list = message[0].split()
		else:
			email_list = self.pop.list()[1]

		return email_list

	def check_imap_uidvalidity(self, folder):
		# compare the UIDVALIDITY of email account and imap server
		uid_validity = self.settings.uid_validity

		response, message = self.imap.status(folder, "(UIDVALIDITY UIDNEXT)")
		current_uid_validity = self.parse_imap_response("UIDVALIDITY", message[0]) or 0

		uidnext = int(self.parse_imap_response("UIDNEXT", message[0]) or "1")
		frappe.db.set_value("Email Account", self.settings.email_account, "uidnext", uidnext)

		if not uid_validity or uid_validity != current_uid_validity:
			# uidvalidity changed & all email uids are reindexed by server
			frappe.db.set_value(
				"Communication",
				{"communication_medium": "Email", "email_account": self.settings.email_account},
				"uid",
				-1,
				update_modified=False,
			)

			if self.settings.use_imap:
				# Remove {"} quotes that are added to handle spaces in IMAP Folder names
				if folder[0] == folder[-1] == '"':
					folder = folder[1:-1]

				frappe.db.set_value(
					"IMAP Folder",
					{"parent": self.settings.email_account_name, "folder_name": folder},
					{"uidvalidity": current_uid_validity, "uidnext": uidnext},
					update_modified=False,
				)
			else:
				frappe.db.set_value(
					"Email Account",
					self.settings.email_account_name,
					{"uidvalidity": current_uid_validity, "uidnext": uidnext},
					update_modified=False,
				)

			sync_count = 100 if uid_validity else int(self.settings.initial_sync_count)
			from_uid = 1 if uidnext < (sync_count + 1) or (uidnext - sync_count) < 1 else uidnext - sync_count
			# sync last 100 email
			self.settings.email_sync_rule = f"UID {from_uid}:{uidnext}"
			self.uid_reindexed = True

	def parse_imap_response(self, cmd, response):
		pattern = rf"(?<={cmd} )[0-9]*"
		match = re.search(pattern, response.decode("utf-8"), re.U | re.I)

		return match[0] if match else None

	def retrieve_message(self, uid, msg_num, folder):
		try:
			if cint(self.settings.use_imap):
				status, message = self.imap.uid("fetch", uid, "(BODY.PEEK[] BODY.PEEK[HEADER] FLAGS)")
				raw = message[0]

				self.get_email_seen_status(uid, raw[0])
				self.latest_messages.append(raw[1])
			else:
				msg = self.pop.retr(msg_num)
				self.latest_messages.append(b"\n".join(msg[1]))
		except _socket.timeout:
			# propagate this error to break the loop
			raise
		except imaplib.IMAP4.abort:
			if self.retry_count < self.retry_limit:
				self.connect()
				self.get_messages(folder)
				self.retry_count += 1
		except Exception as e:
			if self.has_login_limit_exceeded(e):
				raise LoginLimitExceeded(e) from e

			frappe.log_error("Unable to fetch email", self.make_error_msg(uid, msg_num))

		self._post_retrieve_cleanup(uid, msg_num)

	def get_email_seen_status(self, uid, flag_string):
		"""parse the email FLAGS response"""
		if not flag_string or not isinstance(flag_string, str | bytes):
			return None

		flags = []
		for flag in imaplib.ParseFlags(flag_string) or []:
			match = WORDS_PATTERN.search(frappe.as_unicode(flag))
			flags.append(match.group(0))

		if "Seen" in flags:
			self.seen_status.update({uid: "SEEN"})
		else:
			self.seen_status.update({uid: "UNSEEN"})

	def has_login_limit_exceeded(self, e):
		return "-ERR Exceeded the login limit" in strip(cstr(e))

	def _post_retrieve_cleanup(self, uid, msg_num):
		with suppress(Exception):
			if not cint(self.settings.use_imap):
				self.pop.dele(msg_num)
			elif self.settings.email_sync_rule == "UNSEEN":
				self.imap.uid("STORE", uid, "+FLAGS", "(\\SEEN)")

	def is_temporary_system_problem(self, e):
		messages = (
			"-ERR [SYS/TEMP] Temporary system problem. Please try again later.",
			"Connection timed out",
		)
		return any(
			message in strip(cstr(e)) or message in strip(cstr(getattr(e, "strerror", "")))
			for message in messages
		)

	def make_error_msg(self, uid, msg_num):
		partial_mail = None
		traceback = frappe.get_traceback(with_context=True)
		with suppress(Exception):
			# retrieve headers
			if not cint(self.settings.use_imap):
				headers = b"\n".join(self.pop.top(msg_num, 5)[1])
			else:
				headers = self.imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")[1][0][1]

			partial_mail = Email(headers)

		if partial_mail:
			return f"""
Date: {partial_mail.date}
From: {partial_mail.from_email}
Subject: {partial_mail.subject}


Traceback:
{traceback}
"""

		return traceback

	def update_flag(self, folder, uid_list=None):
		"""set all uids mails the flag as seen"""
		if not uid_list:
			return

		if not self.connect():
			return

		self.imap.select(folder)
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
		if isinstance(content, bytes):
			self.mail = email.message_from_bytes(content)
		else:
			self.mail = email.message_from_string(content)

		self.raw_message = content
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
				utc_dt = datetime.datetime.fromtimestamp(utc, tz=datetime.timezone.utc)
				self.date = convert_utc_to_system_timezone(utc_dt).strftime("%Y-%m-%d %H:%M:%S")
			except Exception:
				self.date = now()
		else:
			self.date = now()
		if self.date > now():
			self.date = now()

	@property
	def in_reply_to(self):
		in_reply_to = self.mail.get("In-Reply-To") or ""
		return get_string_between("<", in_reply_to, ">")

	def parse(self):
		"""Walk and process multi-part email."""
		for part in self.mail.walk():
			self.process_part(part)

	def set_subject(self):
		"""Parse and decode `Subject` header."""
		_subject = decode_header(self.mail.get("Subject", "No Subject"))
		self.subject = _subject[0][0] or ""

		if charset := _subject[0][1]:
			# Encoding is known by decode_header (might also be unknown-8bit)
			self.subject = safe_decode(self.subject, charset, ALTERNATE_CHARSET_MAP)

		if isinstance(self.subject, bytes):
			# Fall back to utf-8 if the charset is unknown or decoding fails
			# Replace invalid characters with '<?>'
			self.subject = self.subject.decode("utf-8", "replace")

		# Convert non-string (e.g. None)
		# Truncate to 140 chars (can be used as a document name)
		self.subject = str(self.subject).strip()[:140] or "No Subject"

	def set_from(self):
		# gmail mailing-list compatibility
		# use X-Original-Sender if available, as gmail sometimes modifies the 'From'
		_from_email = self.decode_email(self.mail.get("X-Original-From") or self.mail["From"])
		_reply_to = self.decode_email(self.mail.get("Reply-To"))

		if _reply_to and not frappe.db.get_value(
			"Email Account", {"email_id": _reply_to, "enable_incoming": 1}, "email_id"
		):
			self.from_email = extract_email_id(_reply_to)
		else:
			self.from_email = extract_email_id(_from_email)

		if self.from_email:
			self.from_email = self.from_email.lower()

		self.from_real_name = parse_addr(_from_email)[0] if "@" in _from_email else _from_email

	@staticmethod
	def decode_email(email: bytes | str | None) -> str | None:
		if not email:
			return
		email = frappe.as_unicode(email)
		try:
			parts = decode_header(email)
		except HeaderParseError:
			# Fallback: grab just the email addresses
			emails = re.findall(r"(<.*?>)", email)
			return ", ".join(emails)

		decoded = ""
		for part, encoding in parts:
			if encoding:
				decoded += part.decode(encoding, "replace")
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

			# attach txt file from received email as well aside from saving to text_content if it has filename
			if part.get_filename():
				self.get_attachment(part)

		elif content_type == "text/html":
			self.html_content += self.get_payload(part)

		elif content_type == "message/rfc822":
			# sent by outlook when another email is sent as an attachment to this email
			self.show_attached_email_headers_in_content(part)

		elif part.get_filename() or "image" in content_type:
			self.get_attachment(part)

	def show_attached_email_headers_in_content(self, part):
		# get the multipart/alternative message
		from html import escape

		message = list(part.walk())[1]
		headers = []
		for key in ("From", "To", "Subject", "Date"):
			value = cstr(message.get(key))
			if value:
				headers.append(f"{_(key)}: {escape(value)}")

		self.text_content += "\n".join(headers)
		self.html_content += "<hr>" + "\n".join(f"<p>{h}</p>" for h in headers)

		if not message.is_multipart() and message.get_content_type() == "text/plain":
			# email.parser didn't parse it!
			text_content = self.get_payload(message)
			self.text_content += text_content
			self.html_content += markdown(text_content)

	def get_charset(self, part):
		return part.get_content_charset() or chardet.detect(safe_encode(cstr(part)))["encoding"]

	def get_payload(self, part):
		charset = self.get_charset(part)
		try:
			return str(part.get_payload(decode=True), str(charset), "ignore")
		except LookupError:
			try:
				return str(
					part.get_payload(decode=True), ALTERNATE_CHARSET_MAP.get(charset, "utf-8"), "ignore"
				)
			except Exception:
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
			# Don't clobber existing filename
			while fname in self.cid_map:
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
						"file_name": unquote(attachment["fname"]),
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
		l = THREAD_ID_PATTERN.findall(self.subject)
		return (l and l[0]) or None

	def is_reply(self):
		return bool(self.in_reply_to)


class InboundMail(Email):
	"""Class representation of incoming mail along with mail handlers."""

	def __init__(self, content, email_account, uid=None, seen_status=None, append_to=None):
		super().__init__(content)
		self.email_account = email_account
		self.uid = uid or -1
		self.append_to = append_to
		self.seen_status = seen_status or 0

		# System documents related to this mail
		self._parent_email_queue = None
		self._parent_communication = None
		self._reference_document = None

		self.flags = frappe._dict()

	def get_content(self):
		if self.content_type == "text/html":
			return clean_email_html(self.content)

	def process(self):
		"""Create communication record from email."""
		if self.is_sender_same_as_receiver() and not self.is_reply():
			if frappe.flags.in_test:
				print("WARN: Cannot pull email. Sender same as recipient inbox")
			raise SentEmailInInboxError

		communication = self.is_exist_in_system()
		if communication:
			communication.update_db(uid=self.uid)
			data = self.as_dict()
			if data.get("bcc") and not communication.bcc:
				communication.update_db(bcc=data.get("bcc"))
			communication.reload()
			return communication

		self.flags.is_new_communication = True
		return self._build_communication_doc()

	def _build_communication_doc(self):
		data = self.as_dict()
		data["doctype"] = "Communication"

		if self.parent_communication():
			data["in_reply_to"] = self.parent_communication().name

		append_to = self.append_to if self.email_account.use_imap else self.email_account.append_to

		if self.reference_document():
			data["reference_doctype"] = self.reference_document().doctype
			data["reference_name"] = self.reference_document().name
		elif append_to and append_to != "Communication":
			reference_name = self._create_reference_document(append_to)
			if reference_name:
				data["reference_doctype"] = append_to
				data["reference_name"] = reference_name

		if self.is_notification():
			# Disable notifications for notification.
			data["unread_notification_sent"] = 1

		if self.seen_status:
			data["_seen"] = json.dumps(self.get_users_linked_to_account(self.email_account))

		communication = frappe.get_doc(data)
		communication.flags.in_receive = True
		communication.insert(ignore_permissions=True)

		# Communication might have been modified by some hooks, reload before saving
		communication.reload()

		# save attachments
		communication._attachments = self.save_attachments_in_doc(communication)
		communication.content = sanitize_html(self.replace_inline_images(communication._attachments))
		communication.save()
		return communication

	def replace_inline_images(self, attachments):
		# replace inline images
		content = self.content
		for file in attachments:
			if self.cid_map.get(file.name):
				content = content.replace(f"cid:{self.cid_map[file.name]}", file.unique_url)
		return content

	def is_notification(self):
		isnotification = self.mail.get("isnotification")
		return isnotification and ("notification" in isnotification)

	def is_exist_in_system(self):
		"""Check if this email already exists in the system(as communication document)."""
		from frappe.core.doctype.communication.communication import Communication

		if not self.message_id:
			return

		return Communication.find_one_by_filters(message_id=self.message_id, order_by="creation DESC")

	def is_sender_same_as_receiver(self):
		return self.from_email == self.email_account.email_id

	def is_reply_to_system_sent_mail(self):
		"""Is it a reply to already sent mail."""
		return self.is_reply() and frappe.local.site in self.in_reply_to

	def parent_email_queue(self):
		"""Get parent record from `Email Queue`.

		If it is a reply to already sent mail, then there will be a parent record in EMail Queue.
		"""
		from frappe.email.doctype.email_queue.email_queue import EmailQueue

		if self._parent_email_queue is not None:
			return self._parent_email_queue

		parent_email_queue = ""
		if self.is_reply_to_system_sent_mail():
			parent_email_queue = EmailQueue.find_one_by_filters(message_id=self.in_reply_to)

		self._parent_email_queue = parent_email_queue or ""
		return self._parent_email_queue

	def parent_communication(self):
		"""Find a related communication so that we can prepare a mail thread.

		The way it happens is by using in-reply-to header, and we can't make thread if it does not exist.

		Here are the cases to handle:
		1. If mail is a reply to already sent mail, then we can get parent communicaion from
		        Email Queue record or message_id on communication.
		2. Sometimes we send communication name in message-ID directly, use that to get parent communication.
		3. Sender sent a reply but reply is on top of what (s)he sent before,
		        then parent record exists directly in communication.
		"""
		from frappe.core.doctype.communication.communication import Communication

		if self._parent_communication is not None:
			return self._parent_communication

		if not self.is_reply():
			return ""

		communication = Communication.find_one_by_filters(message_id=self.in_reply_to)
		if not communication:
			if self.parent_email_queue() and self.parent_email_queue().communication:
				communication = Communication.find(self.parent_email_queue().communication, ignore_error=True)
			else:
				reference = self.in_reply_to
				if "@" in self.in_reply_to:
					reference, _ = self.in_reply_to.split("@", 1)
				communication = Communication.find(reference, ignore_error=True)

		self._parent_communication = communication or ""
		return self._parent_communication

	def reference_document(self):
		"""Reference document is a document to which mail relate to.

		We can get reference document from Parent record(EmailQueue | Communication) if exists.
		Otherwise we do subject match to find reference document if we know the reference(append_to) doctype.
		"""
		if self._reference_document is not None:
			return self._reference_document

		reference_document = ""
		parent = self.parent_email_queue() or self.parent_communication()

		if parent and parent.reference_doctype:
			reference_doctype, reference_name = parent.reference_doctype, parent.reference_name
			reference_document = self.get_doc(reference_doctype, reference_name, ignore_error=True)

		if not reference_document and self.email_account.append_to:
			reference_document = self.match_record_by_subject_and_sender(self.email_account.append_to)

		self._reference_document = reference_document or ""
		return self._reference_document

	def get_reference_name_from_subject(self):
		"""
		Ex: "Re: Your email (#OPP-2020-2334343)"
		"""
		return self.subject.rsplit("#", 1)[-1].strip(" ()")

	def match_record_by_subject_and_sender(self, doctype):
		"""Find a record in the given doctype that matches with email subject and sender.

		Cases:
		1. Sometimes record name is part of subject. We can get document by parsing name from subject
		2. Find by matching sender and subject
		3. Find by matching subject alone (Special case)
		        Ex: when a System User is using Outlook and replies to an email from their own client,
		        it reaches the Email Account with the threading info lost and the (sender + subject match)
		        doesn't work because the sender in the first communication was someone different to whom
		        the system user is replying to via the common email account in Frappe. This fix bypasses
		        the sender match when the sender is a system user and subject is atleast 10 chars long
		        (for additional safety)

		NOTE: We consider not to match by subject if match record is very old.
		"""
		name = self.get_reference_name_from_subject()
		email_fields = self.get_email_fields(doctype)

		record = self.get_doc(doctype, name, ignore_error=True) if name else None

		if not record:
			subject = self.clean_subject(self.subject)
			filters = {
				email_fields.subject_field: ("like", f"%{subject}%"),
				"creation": (">", self.get_relative_dt(days=-60)),
			}

			# Sender check is not needed incase mail is from system user.
			if not (len(subject) > 10 and is_system_user(self.from_email)):
				filters[email_fields.sender_field] = self.from_email

			name = frappe.db.get_value(self.email_account.append_to, filters=filters)
			record = self.get_doc(doctype, name, ignore_error=True) if name else None
		return record

	def _create_reference_document(self, doctype):
		"""Create reference document if it does not exist in the system."""
		parent = frappe.new_doc(doctype)
		email_fields = self.get_email_fields(doctype)

		if email_fields.subject_field:
			parent.set(email_fields.subject_field, frappe.as_unicode(self.subject)[:140])

		if email_fields.sender_field:
			parent.set(email_fields.sender_field, frappe.as_unicode(self.from_email))

		if email_fields.sender_name_field:
			parent.set(email_fields.sender_name_field, frappe.as_unicode(self.from_real_name))

		parent.flags.ignore_mandatory = True

		try:
			parent.insert(ignore_permissions=True)
			return parent.name
		except frappe.DuplicateEntryError:
			# try and find matching parent
			return frappe.db.get_value(doctype, {email_fields.sender_field: self.from_email})

	@staticmethod
	def get_doc(doctype, docname, ignore_error=False):
		try:
			return frappe.get_doc(doctype, docname)
		except frappe.DoesNotExistError:
			if ignore_error:
				return
			raise

	@staticmethod
	def get_relative_dt(days):
		"""Get relative to current datetime. Only relative days are supported."""
		return add_days(get_datetime(), days)

	@staticmethod
	def get_users_linked_to_account(email_account):
		"""Get list of users who linked to Email account."""
		users = frappe.get_all("User Email", filters={"email_account": email_account.name}, fields=["parent"])
		return list({user.get("parent") for user in users})

	@staticmethod
	def clean_subject(subject):
		"""Remove Prefixes like 'fw', FWD', 're' etc from subject."""
		# Match strings like "fw:", "re	:" etc.
		regex = r"(^\s*(fw|fwd|wg)[^:]*:|\s*(re|aw)[^:]*:\s*)*"
		return frappe.as_unicode(strip(re.sub(regex, "", subject, count=0, flags=re.IGNORECASE)))

	@staticmethod
	def get_email_fields(doctype):
		"""Return Email related fields of a doctype."""
		fields = frappe._dict()

		email_fields = ["subject_field", "sender_field", "sender_name_field"]
		meta = frappe.get_meta(doctype)

		for field in email_fields:
			if hasattr(meta, field):
				fields[field] = getattr(meta, field)
		return fields

	@staticmethod
	def get_document(self, doctype, name):
		"""Is same as frappe.get_doc but suppresses the DoesNotExist error."""
		try:
			return frappe.get_doc(doctype, name)
		except frappe.DoesNotExistError:
			return None

	def as_dict(self):
		""" """
		return {
			"subject": self.subject,
			"content": self.get_content(),
			"text_content": self.text_content,
			"sent_or_received": "Received",
			"sender_full_name": self.from_real_name,
			"sender": self.from_email,
			"recipients": self.decode_email(self.mail.get("To") or ""),
			"cc": self.decode_email(self.mail.get("CC") or ""),
			"bcc": self.decode_email(self.mail.get("BCC") or ""),
			"email_account": self.email_account.name,
			"communication_medium": "Email",
			"uid": self.uid,
			"message_id": self.message_id,
			"communication_date": self.date,
			"has_attachment": 1 if self.attachments else 0,
			"seen": self.seen_status or 0,
		}
