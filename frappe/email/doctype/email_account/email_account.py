# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, cint
from frappe.email.smtp import SMTPServer
from frappe.email.receive import POP3Server, Email

class EmailAccount(Document):
	def validate(self):
		if self.email_id and not validate_email_add(self.email_id):
			frappe.throw(_("{0} is not a valid email id").format(self.email_id),
				frappe.InvalidEmailAddressError)

		self.there_must_be_atleast_one_default()
		self.check_smtp()
		self.append_to_must_have_subject_and_status()

		if self.enabled:
			self.get_pop3()

	def on_update(self):
		self.there_must_be_only_one_default()

	def there_must_be_atleast_one_default(self):
		if not frappe.db.get_value("Email Account", {"is_default": 1}):
			if not self.is_default:
				self.is_default = 1
				frappe.msgprint(_("Setting as Default"))

	def there_must_be_only_one_default(self):
		if self.is_default:
			for email_account in frappe.get_list("Email Account",
				{"is_default": 1}, ignore_permissions=True):
				if email_account.name==self.name:
					continue
				email_account = frappe.get_doc("Email Account",
					email_account.name)
				email_account.is_default = 0
				email_account.save()

	def append_to_must_have_subject_and_status(self):
		if self.append_to:
			meta = frappe.get_meta(self.append_to)
			if not (meta.has_field("subject") and meta.has_field("status")):
				frappe.throw(_("Append To DocType must have fields 'Subject' and 'Status'"))

	def check_smtp(self):
		if self.enable_outgoing and self.smtp_server \
			and not frappe.local.flags.in_patch:
			SMTPServer(login = self.email_id,
				password = self.password,
				server = self.smtp_server,
				port = cint(self.smtp_port),
				use_ssl = cint(self.use_tls)
			)

	def get_pop3(self):
		args = {
			"host": self.smtp_server,
			"use_ssl": self.use_ssl,
			"username": self.email_id,
			"password": self.password
		}

		pop3 = POP3Server(args)
		pop3.connect()
		return pop3

	def receive(self):
		if self.enabled:
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
					"recipients": email.get("To"),
					"email_account": self.name
				})

				self.set_thread(communication, email)

				communication.insert(ignore_permissions = 1)

				# save attachments
				email.save_attachments_in_doc(communication)

	def set_thread(self, communication, email):
		in_reply_to = (email.get("In-Reply-To") or "").strip(" <>")
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
			parent = self.new_doc(self.append_to)
			parent.subject = email.subject
			parent.ignore_mandatory = True
			parent.insert(ignore_permissions=True)

		if not parent:
			parent = self

		if parent:
			communication.reference_doctype = parent.doctype
			communication.reference_name = parent.name
