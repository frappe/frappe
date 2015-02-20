# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, cint
from frappe.email.smtp import SMTPServer
from frappe.email.receive import POP3Server, Email
from poplib import error_proto
import markdown2

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
		if self.email_id and not validate_email_add(self.email_id):
			frappe.throw(_("{0} is not a valid email id").format(self.email_id),
				frappe.InvalidEmailAddressError)

		if frappe.local.flags.in_patch or frappe.local.flags.in_test:
			return

		if not frappe.local.flags.in_install and not frappe.local.flags.in_patch:
			if self.enable_incoming:
				self.get_pop3()

			if self.enable_outgoing:
				self.check_smtp()

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

			server = SMTPServer(login = self.email_id,
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
			"username": self.email_id,
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

			for raw in incoming_mails:
				email = Email(raw)

				communication = frappe.get_doc({
					"doctype": "Communication",
					"subject": email.subject,
					"content": email.content,
					"sent_or_received": "Received",
					"sender_full_name": email.from_real_name,
					"sender": email.from_email,
					"recipients": email.mail.get("To"),
					"email_account": self.name,
					"communication_medium": "Email"
				})

				self.set_thread(communication, email)

				communication.insert(ignore_permissions = 1)

				# save attachments
				email.save_attachments_in_doc(communication)

				if self.enable_auto_reply:
					self.send_auto_reply(communication)

				# notify all participants of this thread
				# convert content to HTML - by default text parts of replies are used.
				communication.content = markdown2.markdown(communication.content)
				communication.notify(communication.get_email(), except_sender = True)

	def set_thread(self, communication, email):
		"""Appends communication to parent based on thread ID. Will extract
		parent communication and will link the communication to the reference of that
		communication. Also set the status of parent transaction to Open or Replied.

		If no thread id is found and `append_to` is set for the email account,
		it will create a new parent transaction (e.g. Issue)"""
		in_reply_to = (email.mail.get("In-Reply-To") or "").strip(" <>")
		parent = None
		if in_reply_to:
			if "@" in in_reply_to:

				# reply to a communication sent from the system
				in_reply_to = in_reply_to.split("@", 1)[0]
				if frappe.db.exists("Communication", in_reply_to):
					parent = frappe.get_doc("Communication", in_reply_to)

				if parent.reference_name:
					# parent same as parent of last communication
					parent = frappe.get_doc(parent.reference_doctype,
						parent.reference_name)

		if not parent and self.append_to:
			# no parent found, but must be tagged
			# insert parent type doc
			parent = frappe.new_doc(self.append_to)

			if parent.meta.get_field("subject"):
				parent.subject = email.subject

			if parent.meta.get_field("sender"):
				parent.sender = email.from_email

			if hasattr(parent, "set_subject"):
				parent.set_subject(email.subject)

			if hasattr(parent, "set_sender"):
				parent.set_sender(email.from_email)

			parent.flags.ignore_mandatory = True
			parent.insert(ignore_permissions=True)

		if parent:
			communication.reference_doctype = parent.doctype
			communication.reference_name = parent.name

	def send_auto_reply(self, communication):
		"""Send auto reply if set."""
		if self.auto_reply_message:
			frappe.sendmail(recipients = [communication.from_email],
				sender = self.email_id,
				subject = _("Re: ") + communication.subject,
				content = self.auto_reply_message or\
					 frappe.get_template("templates/emails/auto_reply.html").render(communication.as_dict()),
				bulk=True)


def pull():
	"""Will be called via scheduler, pull emails from all enabled POP3 email accounts."""
	import frappe.tasks
	for email_account in frappe.get_list("Email Account", filters={"enable_incoming": 1}):
		frappe.tasks.pull_from_email_account.delay(frappe.local.site, email_account.name)
		#frappe.tasks.pull_from_email_account(frappe.local.site, email_account.name)
