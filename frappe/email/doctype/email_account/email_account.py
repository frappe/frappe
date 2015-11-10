# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, cint, get_datetime, DATE_FORMAT, strip, comma_or
from frappe.utils.user import is_system_user
from frappe.utils.jinja import render_template
from frappe.email.smtp import SMTPServer
from frappe.email.receive import POP3Server, Email
from poplib import error_proto
import re
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

class SentEmailInInbox(Exception): pass

class EmailAccount(Document):
	def autoname(self):
		"""Set name as `email_account_name` or make title from email id."""
		if not self.email_account_name:
			self.email_account_name = self.email_id.split("@", 1)[0]\
				.replace("_", " ").replace(".", " ").replace("-", " ").title()

			if self.service:
				self.email_account_name = self.email_account_name + " " + self.service

		self.name = self.email_account_name

	def validate(self):
		"""Validate email id and check POP3 and SMTP connections is enabled."""
		if self.email_id:
			validate_email_add(self.email_id, True)

		if self.login_id_is_different:
			if not self.login_id:
				frappe.throw(_("Login Id is required"))
		else:
			self.login_id = None

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		if self.enable_incoming and not self.append_to:
			frappe.throw(_("Append To is mandatory for incoming mails"))

		if not frappe.local.flags.in_install and not frappe.local.flags.in_patch:
			if self.enable_incoming:
				self.get_pop3()

			if self.enable_outgoing:
				self.check_smtp()

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

	def check_smtp(self):
		"""Checks SMTP settings."""
		if self.enable_outgoing:
			if not self.smtp_server:
				frappe.throw(_("{0} is required").format("SMTP Server"))

			server = SMTPServer(login = getattr(self, "login_id", None) \
					or self.email_id,
				password = self.password,
				server = self.smtp_server,
				port = cint(self.smtp_port),
				use_ssl = cint(self.use_tls)
			)
			server.sess

	def get_pop3(self):
		"""Returns logged in POP3 connection object."""
		args = {
			"host": self.pop3_server,
			"use_ssl": self.use_ssl,
			"username": getattr(self, "login_id", None) or self.email_id,
			"password": self.password
		}

		if not self.pop3_server:
			frappe.throw(_("{0} is required").format("POP3 Server"))

		pop3 = POP3Server(frappe._dict(args))
		try:
			pop3.connect()
		except error_proto, e:
			frappe.throw(e.message)

		return pop3

	def receive(self, test_mails=None):
		"""Called by scheduler to receive emails from this EMail account using POP3."""
		if self.enable_incoming:
			if frappe.local.flags.in_test:
				incoming_mails = test_mails
			else:
				pop3 = self.get_pop3()
				incoming_mails = pop3.get_messages()

			exceptions = []
			for raw in incoming_mails:
				try:
					communication = self.insert_communication(raw)

				except SentEmailInInbox:
					frappe.db.rollback()

				except Exception:
					frappe.db.rollback()
					exceptions.append(frappe.get_traceback())

				else:
					frappe.db.commit()
					attachments = [d.file_name for d in communication._attachments]
					communication.notify(attachments=attachments, fetched_from_email_account=True)

			if exceptions:
				raise Exception, frappe.as_json(exceptions)

	def insert_communication(self, raw):
		email = Email(raw)

		if email.from_email == self.email_id:
			# gmail shows sent emails in inbox
			# and we don't want emails sent by us to be pulled back into the system again
			raise SentEmailInInbox

		communication = frappe.get_doc({
			"doctype": "Communication",
			"subject": email.subject,
			"content": email.content,
			"sent_or_received": "Received",
			"sender_full_name": email.from_real_name,
			"sender": email.from_email,
			"recipients": email.mail.get("To"),
			"cc": email.mail.get("CC"),
			"email_account": self.name,
			"communication_medium": "Email"
		})

		self.set_thread(communication, email)

		communication.insert(ignore_permissions = 1)

		# save attachments
		communication._attachments = email.save_attachments_in_doc(communication)

		# replace inline images
		dirty = False
		for file in communication._attachments:
			if file.name in email.cid_map and email.cid_map[file.name]:
				dirty = True
				communication.content = communication.content.replace("cid:{0}".format(email.cid_map[file.name]),
					file.file_url)

		if dirty:
			# not sure if using save() will trigger anything
			communication.db_set("content", communication.content)

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
		in_reply_to = (email.mail.get("In-Reply-To") or "").strip(" <>")
		parent = None

		if self.append_to:
			# set subject_field and sender_field
			meta_module = frappe.get_meta_module(self.append_to)
			meta = frappe.get_meta(self.append_to)
			subject_field = getattr(meta_module, "subject_field", "subject")
			if not meta.get_field(subject_field):
				subject_field = None
			sender_field = getattr(meta_module, "sender_field", "sender")
			if not meta.get_field(sender_field):
				sender_field = None

		if in_reply_to:
			if "@{0}".format(frappe.local.site) in in_reply_to:

				# reply to a communication sent from the system
				in_reply_to, domain = in_reply_to.split("@", 1)

				if frappe.db.exists("Communication", in_reply_to):
					parent = frappe.get_doc("Communication", in_reply_to)

					# set in_reply_to of current communication
					communication.in_reply_to = in_reply_to

					if parent.reference_name:
						parent = frappe.get_doc(parent.reference_doctype,
							parent.reference_name)

		if not parent and self.append_to and sender_field:
			if subject_field:
				# try and match by subject and sender
				# if sent by same sender with same subject,
				# append it to old coversation
				subject = strip(re.sub("^\s*(Re|RE)[^:]*:\s*", "", email.subject))

				parent = frappe.db.get_all(self.append_to, filters={
					sender_field: email.from_email,
					subject_field: ("like", "%{0}%".format(subject)),
					"creation": (">", (get_datetime() - relativedelta(days=10)).strftime(DATE_FORMAT))
				}, fields="name")

				# match only subject field
				# when the from_email is of a user in the system
				# and subject is atleast 10 chars long
				if not parent and len(subject) > 10 and is_system_user(email.from_email):
					parent = frappe.db.get_all(self.append_to, filters={
						subject_field: ("like", "%{0}%".format(subject)),
						"creation": (">", (get_datetime() - relativedelta(days=10)).strftime(DATE_FORMAT))
					}, fields="name")

			if parent:
				parent = frappe.get_doc(self.append_to, parent[0].name)

		if not parent and self.append_to and self.append_to!="Communication":
			# no parent found, but must be tagged
			# insert parent type doc
			parent = frappe.new_doc(self.append_to)

			if subject_field:
				parent.set(subject_field, email.subject)

			if sender_field:
				parent.set(sender_field, email.from_email)

			parent.flags.ignore_mandatory = True

			try:
				parent.insert(ignore_permissions=True)
			except frappe.DuplicateEntryError:
				# try and find matching parent
				parent_name = frappe.db.get_value(self.append_to, {sender_field: email.from_email})
				if parent_name:
					parent.name = parent_name
				else:
					parent = None

			# NOTE if parent isn't found and there's no subject match, it is likely that it is a new conversation thread and hence is_first = True
			communication.is_first = True

		if parent:
			communication.reference_doctype = parent.doctype
			communication.reference_name = parent.name

	def send_auto_reply(self, communication, email):
		"""Send auto reply if set."""
		if self.enable_auto_reply:
			communication.set_incoming_outgoing_accounts()

			frappe.sendmail(recipients = [email.from_email],
				sender = self.email_id,
				reply_to = communication.incoming_email_account,
				subject = _("Re: ") + communication.subject,
				content = render_template(self.auto_reply_message or "", communication.as_dict()) or \
					 frappe.get_template("templates/emails/auto_reply.html").render(communication.as_dict()),
				reference_doctype = communication.reference_doctype,
				reference_name = communication.reference_name,
				message_id = communication.name,
				unsubscribe_message = _("Leave this conversation"),
				bulk=True)

	def get_unreplied_notification_emails(self):
		"""Return list of emails listed"""
		self.send_notification_to = self.send_notification_to.replace(",", "\n")
		out = [e.strip() for e in self.send_notification_to.split("\n")]
		return out

	def on_trash(self):
		"""Clear communications where email account is linked"""
		frappe.db.sql("update `tabCommunication` set email_account='' where email_account=%s", self.name)

@frappe.whitelist()
def get_append_to(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	if not txt: txt = ""
	return [[d] for d in frappe.get_hooks("email_append_to") if txt in d]

def pull(now=False):
	"""Will be called via scheduler, pull emails from all enabled POP3 email accounts."""
	import frappe.tasks
	for email_account in frappe.get_list("Email Account", filters={"enable_incoming": 1}):
		#frappe.tasks.pull_from_email_account(frappe.local.site, email_account.name)
		if now:
			frappe.tasks.pull_from_email_account(frappe.local.site, email_account.name)
		else:
			frappe.tasks.pull_from_email_account.delay(frappe.local.site, email_account.name)

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
					"creation": ("<", datetime.now() - timedelta(seconds = (email_account.unreplied_for_mins or 30) * 60)),
					"creation": (">", datetime.now() - timedelta(seconds = (email_account.unreplied_for_mins or 30) * 60 * 3))
				}):
				comm = frappe.get_doc("Communication", comm.name)

				if frappe.db.get_value(comm.reference_doctype, comm.reference_name, "status")=="Open":
					# if status is still open
					frappe.sendmail(recipients=email_account.get_unreplied_notification_emails(),
						content=comm.content, subject=comm.subject, doctype= comm.reference_doctype,
						name=comm.reference_name, bulk=True)

				# update flag
				comm.db_set("unread_notification_sent", 1)
