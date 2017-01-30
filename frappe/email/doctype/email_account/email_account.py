# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import imaplib
import re
import socket
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, cint, get_datetime, DATE_FORMAT, strip, comma_or, sanitize_html
from frappe.utils.user import is_system_user
from frappe.utils.jinja import render_template
from frappe.email.smtp import SMTPServer
from frappe.email.receive import EmailServer, Email
from poplib import error_proto
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from frappe.desk.form import assign_to
from frappe.utils.user import get_system_managers
from frappe.utils.background_jobs import enqueue, get_jobs
from frappe.core.doctype.communication.email import set_incoming_outgoing_accounts
from frappe.utils.scheduler import log

class SentEmailInInbox(Exception): pass

class EmailAccount(Document):
	def autoname(self):
		"""Set name as `email_account_name` or make title from Email Address."""
		if not self.email_account_name:
			self.email_account_name = self.email_id.split("@", 1)[0]\
				.replace("_", " ").replace(".", " ").replace("-", " ").title()

		self.name = self.email_account_name

	def validate(self):
		"""Validate Email Address and check POP3/IMAP and SMTP connections is enabled."""
		if self.email_id:
			validate_email_add(self.email_id, True)

		if self.login_id_is_different:
			if not self.login_id:
				frappe.throw(_("Login Id is required"))
		else:
			self.login_id = None

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		#if self.enable_incoming and not self.append_to:
		#	frappe.throw(_("Append To is mandatory for incoming mails"))

		if (not self.awaiting_password and not frappe.local.flags.in_install
			and not frappe.local.flags.in_patch):
			if self.password:
				if self.enable_incoming:
					self.get_incoming_server()
					self.no_failed = 0


				if self.enable_outgoing:
					self.check_smtp()
			else:
				if self.enable_incoming or self.enable_outgoing:
					frappe.throw(_("Password is required or select Awaiting Password"))

		if self.notify_if_unreplied:
			if not self.send_notification_to:
				frappe.throw(_("{0} is mandatory").format(self.meta.get_label("send_notification_to")))
			for e in self.get_unreplied_notification_emails():
				validate_email_add(e, True)

		if self.enable_incoming and self.append_to:
			valid_doctypes = [d[0] for d in get_append_to()]
			if self.append_to not in valid_doctypes:
				frappe.throw(_("Append To can be one of {0}").format(comma_or(valid_doctypes)))



	def on_update(self):
		"""Check there is only one default of each type."""
		self.there_must_be_only_one_default()
		if self.awaiting_password:
			# push values to user_emails
			frappe.db.sql("""UPDATE `tabUser Email` SET awaiting_password = 1
						  WHERE email_account = %(account)s""", {"account": self.name})
		else:
			frappe.db.sql("""UPDATE `tabUser Email` SET awaiting_password = 0
									  WHERE email_account = %(account)s""", {"account": self.name})
		from frappe.core.doctype.user.user import ask_pass_update
		ask_pass_update()

	def there_must_be_only_one_default(self):
		"""If current Email Account is default, un-default all other accounts."""
		for fn in ("default_incoming", "default_outgoing"):
			if self.get(fn):
				for email_account in frappe.get_all("Email Account",
					filters={fn: 1}):
					if email_account.name==self.name:
						continue
					email_account = frappe.get_doc("Email Account",
						email_account.name)
					email_account.set(fn, 0)
					email_account.save()

	@frappe.whitelist()
	def get_domain(self,email_id):
		"""look-up the domain and then full"""
		try:
			domain = email_id.split("@")
			return frappe.db.sql("""select name,use_imap,email_server,use_ssl,smtp_server,use_tls,smtp_port
			from `tabEmail Domain`
			where name = %s
			""",domain[1],as_dict=1)
		except Exception:
			pass

	def check_smtp(self):
		"""Checks SMTP settings."""
		if self.enable_outgoing:
			if not self.smtp_server:
				frappe.throw(_("{0} is required").format("SMTP Server"))

			server = SMTPServer(login = getattr(self, "login_id", None) \
					or self.email_id,
				server = self.smtp_server,
				port = cint(self.smtp_port),
				use_tls = cint(self.use_tls)
			)
			if self.password:
				server.password = self.get_password()
			server.sess

	def get_incoming_server(self, in_receive=False):
		"""Returns logged in POP3/IMAP connection object."""
		if frappe.cache().get_value("workers:no-internet") == True:
			return None

		args = frappe._dict({
			"email_account":self.name,
			"host": self.email_server,
			"use_ssl": self.use_ssl,
			"username": getattr(self, "login_id", None) or self.email_id,
			"use_imap": self.use_imap,
		})
		if self.password:
			args.password = self.get_password()

		if not args.get("host"):
			frappe.throw(_("{0} is required").format("Email Server"))

		email_server = EmailServer(frappe._dict(args))
		try:
			email_server.connect()
		except (error_proto, imaplib.IMAP4.error), e:
			if in_receive and ("authentication failed" in e.message.lower() or "log in via your web browser" in e.message.lower()):
				# if called via self.receive and it leads to authentication error, disable incoming
				# and send email to system manager
				self.handle_incoming_connect_error(
					description=_('Authentication failed while receiving emails from Email Account {0}. Message from server: {1}'.format(self.name, e.message))
				)

				return None

			else:
				frappe.throw(e.message)

		except socket.error:
			if in_receive:
				# timeout while connecting, see receive.py connect method
				description = frappe.message_log.pop() if frappe.message_log else "Socket Error"
				if test_internet():
					self.db_set("no_failed", self.no_failed + 1)
					if self.no_failed > 2:
						self.handle_incoming_connect_error(description=description)
				else:
					frappe.cache().set_value("workers:no-internet", True)
				return None

			else:
				raise
		if not in_receive:
			if self.use_imap:
				email_server.imap.logout()
		# reset failed attempts count
		self.set_failed_attempts_count(0)

		return email_server

	def handle_incoming_connect_error(self, description):
		if test_internet():
			if self.get_failed_attempts_count() > 2:
				self.db_set("enable_incoming", 0)

				for user in get_system_managers(only_name=True):
					try:
						assign_to.add({
							'assign_to': user,
							'doctype': self.doctype,
							'name': self.name,
							'description': description,
							'priority': 'High',
							'notify': 1
						})
					except assign_to.DuplicateToDoError:
						frappe.message_log.pop()
						pass
			else:
				self.set_failed_attempts_count(self.get_failed_attempts_count() + 1)
		else:
			frappe.cache().set_value("workers:no-internet", True)

	def set_failed_attempts_count(self, value):
		frappe.cache().set('{0}:email-account-failed-attempts'.format(self.name), value)

	def get_failed_attempts_count(self):
		return cint(frappe.cache().get('{0}:email-account-failed-attempts'.format(self.name)))

	def receive(self, test_mails=None):
		"""Called by scheduler to receive emails from this EMail account using POP3/IMAP."""
		if self.enable_incoming:
			exceptions = []
			if frappe.local.flags.in_test:
				incoming_mails = test_mails
			else:
				email_server = self.get_incoming_server(in_receive=True)
				incoming_mails = email_server.get_messages()

			for msg in incoming_mails:
				try:

					communication = self.insert_communication(msg)
					#self.notify_update()

				except SentEmailInInbox:
					frappe.db.rollback()

				except Exception:
					frappe.db.rollback()
					log('email_account.receive')
					if self.use_imap:
						self.handle_bad_emails(email_server, msg[1], msg[0], frappe.get_traceback())
					exceptions.append(frappe.get_traceback())

				else:
					frappe.db.commit()
					attachments = [d.file_name for d in communication._attachments]

					communication.notify(attachments=attachments, fetched_from_email_account=True)

			#notify if user is linked to account
			if len(incoming_mails)>0 and not frappe.local.flags.in_test:
				frappe.publish_realtime('new_email', {"account":self.email_account_name,"number":len(incoming_mails)})

			if exceptions:
				raise Exception, frappe.as_json(exceptions)

	def handle_bad_emails(self, email_server, uid, raw, reason):
		if cint(email_server.settings.use_imap):
			import email
			try:
				mail = email.message_from_string(raw)

				message_id = mail.get('Message-ID')
			except Exception:
				message_id = "can't be parsed"

			unhandled_email = frappe.get_doc({
				"doctype": "Unhandled Email",
				"email_account": email_server.settings.email_account,
				"uid": uid,
				"message_id": message_id,
				"reason":reason
			})
			unhandled_email.save()
			frappe.db.commit()

	def insert_communication(self, msg):
		if isinstance(msg,list):
			raw, uid, seen = msg
		else:
			raw = msg
			seen = uid = None
		email = Email(raw)

		if email.from_email == self.email_id and not email.mail.get("Reply-To"):
			# gmail shows sent emails in inbox
			# and we don't want emails sent by us to be pulled back into the system again
			# dont count emails sent by the system get those
			raise SentEmailInInbox

		communication = frappe.get_doc({
			"doctype": "Communication",
			"subject": email.subject,
			"content": email.content,
			'text_content': email.text_content,
			"sent_or_received": "Received",
			"sender_full_name": email.from_real_name,
			"sender": email.from_email,
			"recipients": email.mail.get("To"),
			"cc": email.mail.get("CC"),
			"email_account": self.name,
			"communication_medium": "Email",
			"uid": uid,
			"message_id": email.message_id,
			"communication_date": email.date,
			"has_attachment": 1 if email.attachments else 0,
			"seen": seen
		})

		self.set_thread(communication, email)

		communication.flags.in_receive = True
		communication.insert(ignore_permissions = 1)

		# save attachments
		communication._attachments = email.save_attachments_in_doc(communication)

		# replace inline images


		dirty = False
		for file in communication._attachments:
			if file.name in email.cid_map and email.cid_map[file.name]:
				dirty = True

				email.content = email.content.replace("cid:{0}".format(email.cid_map[file.name]),
					file.file_url)

		if dirty:
			# not sure if using save() will trigger anything
			communication.db_set("content", sanitize_html(email.content))

		# notify all participants of this thread
		if self.enable_auto_reply and getattr(communication, "is_first", False):
			self.send_auto_reply(communication, email)

		return communication

	def set_thread(self, communication, email):
		"""Appends communication to parent based on thread ID. Will extract
		parent communication and will link the communication to the reference of that
		communication. Also set the status of parent transaction to Open or Replied.

		If no thread id is found and `append_to` is set for the email account,
		it will create a new parent transaction (e.g. Issue)"""
		parent = None

		parent = self.find_parent_from_in_reply_to(communication, email)

		if not parent and self.append_to:
			self.set_sender_field_and_subject_field()

		if not parent and self.append_to:
			parent = self.find_parent_based_on_subject_and_sender(communication, email)

		if not parent and self.append_to and self.append_to!="Communication":
			parent = self.create_new_parent(communication, email)

		if parent:
			communication.reference_doctype = parent.doctype
			communication.reference_name = parent.name

		# check if message is notification and disable notifications for this message
		references = email.mail.get("References")
		if references:
			if "notification" in references:
				communication.unread_notification_sent = 1

	def set_sender_field_and_subject_field(self):
		'''Identify the sender and subject fields from the `append_to` DocType'''
		# set subject_field and sender_field
		meta_module = frappe.get_meta_module(self.append_to)
		meta = frappe.get_meta(self.append_to)

		self.subject_field = getattr(meta_module, "subject_field", "subject")
		if not meta.get_field(self.subject_field):
			self.subject_field = None

		self.sender_field = getattr(meta_module, "sender_field", "sender")
		if not meta.get_field(self.sender_field):
			self.sender_field = None

	def find_parent_based_on_subject_and_sender(self, communication, email):
		'''Find parent document based on subject and sender match'''
		parent = None

		if self.append_to and self.sender_field:
			if self.subject_field:
				# try and match by subject and sender
				# if sent by same sender with same subject,
				# append it to old coversation
				subject = frappe.as_unicode(strip(re.sub("(^\s*(Fw|FW|fwd)[^:]*:|\s*(Re|RE)[^:]*:\s*)*",
					"", email.subject)))

				parent = frappe.db.get_all(self.append_to, filters={
					self.sender_field: email.from_email,
					self.subject_field: ("like", "%{0}%".format(subject)),
					"creation": (">", (get_datetime() - relativedelta(days=10)).strftime(DATE_FORMAT))
				}, fields="name")

				# match only subject field
				# when the from_email is of a user in the system
				# and subject is atleast 10 chars long
				if not parent and len(subject) > 10 and is_system_user(email.from_email):
					parent = frappe.db.get_all(self.append_to, filters={
						self.subject_field: ("like", "%{0}%".format(subject)),
						"creation": (">", (get_datetime() - relativedelta(days=10)).strftime(DATE_FORMAT))
					}, fields="name")

			if parent:
				parent = frappe._dict(doctype=self.append_to, name=parent[0].name)
				return parent


	def create_new_parent(self, communication, email):
		'''If no parent found, create a new reference document'''

		# no parent found, but must be tagged
		# insert parent type doc
		parent = frappe.new_doc(self.append_to)

		if self.subject_field:
			parent.set(self.subject_field, frappe.as_unicode(email.subject))

		if self.sender_field:
			parent.set(self.sender_field, frappe.as_unicode(email.from_email))

		parent.flags.ignore_mandatory = True

		try:
			parent.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			# try and find matching parent
			parent_name = frappe.db.get_value(self.append_to, {self.sender_field: email.from_email})
			if parent_name:
				parent.name = parent_name
			else:
				parent = None

		# NOTE if parent isn't found and there's no subject match, it is likely that it is a new conversation thread and hence is_first = True
		communication.is_first = True

		return parent

	def find_parent_from_in_reply_to(self, communication, email):
		'''Returns parent reference if embedded in In-Reply-To header

		Message-ID is formatted as `{message_id}@{site}`'''
		parent = None
		in_reply_to = (email.mail.get("In-Reply-To") or "").strip(" <>")

		if in_reply_to and "@{0}".format(frappe.local.site) in in_reply_to:
			# reply to a communication sent from the system
			email_queue = frappe.db.get_value('Email Queue', dict(message_id=in_reply_to), ['communication','reference_doctype', 'reference_name'])
			if email_queue:
				parent_communication, parent_doctype, parent_name = email_queue
				if parent_communication:
					communication.in_reply_to = parent_communication
			else:
				reference, domain = in_reply_to.split("@", 1)
				parent_doctype, parent_name = 'Communication', reference

			if frappe.db.exists(parent_doctype, parent_name):
				parent = frappe._dict(doctype=parent_doctype, name=parent_name)

				# set in_reply_to of current communication
				if parent_doctype=='Communication':
					# communication.in_reply_to = email_queue.communication

					if parent.reference_name:
						# the true parent is the communication parent
						parent = frappe.get_doc(parent.reference_doctype,
							parent.reference_name)

		return parent

	def send_auto_reply(self, communication, email):
		"""Send auto reply if set."""
		if self.enable_auto_reply:
			set_incoming_outgoing_accounts(communication)

			if self.send_unsubscribe_message:
				unsubscribe_message = _("Leave this conversation")
			else:
				unsubscribe_message = ""

			frappe.sendmail(recipients = [email.from_email],
				sender = self.email_id,
				reply_to = communication.incoming_email_account,
				subject = _("Re: ") + communication.subject,
				content = render_template(self.auto_reply_message or "", communication.as_dict()) or \
					 frappe.get_template("templates/emails/auto_reply.html").render(communication.as_dict()),
				reference_doctype = communication.reference_doctype,
				reference_name = communication.reference_name,
				in_reply_to = email.mail.get("Message-Id"), # send back the Message-Id as In-Reply-To
				unsubscribe_message = unsubscribe_message)

	def get_unreplied_notification_emails(self):
		"""Return list of emails listed"""
		self.send_notification_to = self.send_notification_to.replace(",", "\n")
		out = [e.strip() for e in self.send_notification_to.split("\n") if e.strip()]
		return out

	def on_trash(self):
		"""Clear communications where email account is linked"""
		frappe.db.sql("update `tabCommunication` set email_account='' where email_account=%s", self.name)

	def after_rename(self, old, new, merge=False):
		frappe.db.set_value("Email Account", new, "email_account_name", new)

@frappe.whitelist()
def get_append_to(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	if not txt: txt = ""
	return [[d] for d in frappe.get_hooks("email_append_to") if txt in d]

def test_internet(host="8.8.8.8", port=53, timeout=3):
	"""Returns True if internet is connected

	Host: 8.8.8.8 (google-public-dns-a.google.com)
	OpenPort: 53/tcp
	Service: domain (DNS/TCP)
	"""
	try:
		socket.setdefaulttimeout(timeout)
		socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
		return True
	except Exception as ex:
		print ex.message
		return False

def notify_unreplied():
	"""Sends email notifications if there are unreplied Communications
		and `notify_if_unreplied` is set as true."""

	for email_account in frappe.get_all("Email Account", "name", filters={"enable_incoming": 1, "notify_if_unreplied": 1}):
		email_account = frappe.get_doc("Email Account", email_account.name)
		if email_account.append_to:

			# get open communications younger than x mins, for given doctype
			for comm in frappe.get_all("Communication", "name", filters={
					"sent_or_received": "Received",
					"reference_doctype": email_account.append_to,
					"unread_notification_sent": 0,
					"email_account":email_account.name,
					"creation": ("<", datetime.now() - timedelta(seconds = (email_account.unreplied_for_mins or 30) * 60)),
					"creation": (">", datetime.now() - timedelta(seconds = (email_account.unreplied_for_mins or 30) * 60 * 3))
				}):
				comm = frappe.get_doc("Communication", comm.name)

				if frappe.db.get_value(comm.reference_doctype, comm.reference_name, "status")=="Open":
					# if status is still open
					frappe.sendmail(recipients=email_account.get_unreplied_notification_emails(),
						content=comm.content, subject=comm.subject, doctype= comm.reference_doctype,
						name=comm.reference_name)

				# update flag
				comm.db_set("unread_notification_sent", 1)

def pull(now=False):
	"""Will be called via scheduler, pull emails from all enabled Email accounts."""
	if frappe.cache().get_value("workers:no-internet") == True:
		if test_internet():
			frappe.cache().set_value("workers:no-internet", False)
		else:
			return
	queued_jobs = get_jobs(site=frappe.local.site, key='job_name')[frappe.local.site]
	for email_account in frappe.get_list("Email Account",
		filters={"enable_incoming": 1, "awaiting_password": 0}):
		if now:
			pull_from_email_account(email_account.name)

		else:
			# job_name is used to prevent duplicates in queue
			job_name = 'pull_from_email_account|{0}'.format(email_account.name)

			if job_name not in queued_jobs:
				enqueue(pull_from_email_account, 'short', event='all', job_name=job_name,
					email_account=email_account.name)

def pull_from_email_account(email_account):
	'''Runs within a worker process'''
	email_account = frappe.get_doc("Email Account", email_account)
	email_account.receive()
