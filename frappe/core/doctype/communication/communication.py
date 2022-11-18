# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

from __future__ import absolute_import, unicode_literals

from collections import Counter
from email.utils import getaddresses
from typing import List

from parse import compile
from six.moves.urllib.parse import unquote

import frappe
from frappe import _
from frappe.automation.doctype.assignment_rule.assignment_rule import (
	apply as apply_assignment_rule,
)
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.core.doctype.comment.comment import update_comment_in_doc
from frappe.core.doctype.communication.email import _notify, notify, validate_email
from frappe.core.utils import get_parent_doc
from frappe.model.document import Document
from frappe.utils import cstr, parse_addr, strip_html, time_diff_in_seconds, validate_email_address
from frappe.utils.bot import BotReply
from frappe.utils.user import is_system_user

exclude_from_linked_with = True


class Communication(Document):
	no_feed_on_delete = True

	"""Communication represents an external communication like Email."""

	def onload(self):
		"""create email flag queue"""
		if (
			self.communication_type == "Communication"
			and self.communication_medium == "Email"
			and self.sent_or_received == "Received"
			and self.uid
			and self.uid != -1
		):

			email_flag_queue = frappe.db.get_value(
				"Email Flag Queue", {"communication": self.name, "is_completed": 0}
			)
			if email_flag_queue:
				return

			frappe.get_doc(
				{
					"doctype": "Email Flag Queue",
					"action": "Read",
					"communication": self.name,
					"uid": self.uid,
					"email_account": self.email_account,
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

	def validate(self):
		self.validate_reference()

		if not self.user:
			self.user = frappe.session.user

		if not self.subject:
			self.subject = strip_html((self.content or "")[:141])

		if not self.sent_or_received:
			self.seen = 1
			self.sent_or_received = "Sent"

		self.set_status()

		validate_email(self)

		if self.communication_medium == "Email":
			self.parse_email_for_timeline_links()
			self.set_timeline_links()
			self.deduplicate_timeline_links()

		self.set_sender_full_name()

	def validate_reference(self):
		if self.reference_doctype and self.reference_name:
			if not self.reference_owner:
				self.reference_owner = frappe.db.get_value(
					self.reference_doctype, self.reference_name, "owner"
				)

			# prevent communication against a child table
			if frappe.get_meta(self.reference_doctype).istable:
				frappe.throw(
					_("Cannot create a {0} against a child document: {1}").format(
						_(self.communication_type), _(self.reference_doctype)
					)
				)

			# Prevent circular linking of Communication DocTypes
			if self.reference_doctype == "Communication":
				circular_linking = False
				doc = get_parent_doc(self)
				while doc.reference_doctype == "Communication":
					if get_parent_doc(doc).name == self.name:
						circular_linking = True
						break
					doc = get_parent_doc(doc)

				if circular_linking:
					frappe.throw(
						_("Please make sure the Reference Communication Docs are not circularly linked."),
						frappe.CircularLinkingError,
					)

	def after_insert(self):
		if not (self.reference_doctype and self.reference_name):
			return

		if self.reference_doctype == "Communication" and self.sent_or_received == "Sent":
			frappe.db.set_value("Communication", self.reference_name, "status", "Replied")

		if self.communication_type == "Communication":
			self.notify_change("add")

		elif self.communication_type in ("Chat", "Notification", "Bot"):
			if self.reference_name == frappe.session.user:
				message = self.as_dict()
				message["broadcast"] = True
				frappe.publish_realtime("new_message", message, after_commit=True)
			else:
				# reference_name contains the user who is addressed in the messages' page comment
				frappe.publish_realtime(
					"new_message", self.as_dict(), user=self.reference_name, after_commit=True
				)

	def set_signature_in_email_content(self):
		"""Set sender's User.email_signature or default outgoing's EmailAccount.signature to the email"""
		if not self.content:
			return

		quill_parser = compile('<div class="ql-editor read-mode">{}</div>')
		email_body = quill_parser.parse(self.content)

		if not email_body:
			return

		email_body = email_body[0]

		user_email_signature = (
			frappe.db.get_value(
				"User",
				self.sender,
				"email_signature",
			)
			if self.sender
			else None
		)

		signature = user_email_signature or frappe.db.get_value(
			"Email Account",
			{"default_outgoing": 1, "add_signature": 1},
			"signature",
		)

		if not signature:
			return

		_signature = quill_parser.parse(signature)[0] if "ql-editor" in signature else None

		if (cstr(_signature) or signature) not in self.content:
			self.content = f'{self.content}</p><br><p class="signature">{signature}'

	def before_save(self):
		if not self.flags.skip_add_signature:
			self.set_signature_in_email_content()

	def on_update(self):
		# add to _comment property of the doctype, so it shows up in
		# comments count for the list view
		update_comment_in_doc(self)

		if self.comment_type != "Updated":
			update_parent_document_on_communication(self)
			self.bot_reply()

	def on_trash(self):
		if self.communication_type == "Communication":
			self.notify_change("delete")

	def notify_change(self, action):
		frappe.publish_realtime(
			"docinfo_update",
			{"doc": self.as_dict(), "key": "communications", "action": action},
			doctype=self.reference_doctype,
			docname=self.reference_name,
			after_commit=True,
		)

	def set_status(self):
		if not self.is_new():
			return

		if self.reference_doctype and self.reference_name:
			self.status = "Linked"
		elif self.communication_type == "Communication":
			self.status = "Open"
		else:
			self.status = "Closed"

		# set email status to spam
		email_rule = frappe.db.get_value("Email Rule", {"email_id": self.sender, "is_spam": 1})
		if (
			self.communication_type == "Communication"
			and self.communication_medium == "Email"
			and self.sent_or_received == "Sent"
			and email_rule
		):

			self.email_status = "Spam"

	def set_sender_full_name(self):
		if not self.sender_full_name and self.sender:
			if self.sender == "Administrator":
				self.sender_full_name = frappe.db.get_value("User", "Administrator", "full_name")
				self.sender = frappe.db.get_value("User", "Administrator", "email")
			elif self.sender == "Guest":
				self.sender_full_name = self.sender
				self.sender = None
			else:
				if self.sent_or_received == "Sent":
					validate_email_address(self.sender, throw=True)
				sender_name, sender_email = parse_addr(self.sender)
				if sender_name == sender_email:
					sender_name = None

				self.sender = sender_email
				self.sender_full_name = sender_name

				if not self.sender_full_name:
					self.sender_full_name = frappe.db.get_value("User", self.sender, "full_name")

				if not self.sender_full_name:
					first_name, last_name = frappe.db.get_value(
						"Contact", filters={"email_id": sender_email}, fieldname=["first_name", "last_name"]
					) or [None, None]
					self.sender_full_name = (first_name or "") + (last_name or "")

				if not self.sender_full_name:
					self.sender_full_name = sender_email

	def send(
		self, print_html=None, print_format=None, attachments=None, send_me_a_copy=False, recipients=None
	):
		"""Send communication via Email.

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		self.send_me_a_copy = send_me_a_copy
		self.notify(print_html, print_format, attachments, recipients)

	def notify(
		self,
		print_html=None,
		print_format=None,
		attachments=None,
		recipients=None,
		cc=None,
		bcc=None,
		fetched_from_email_account=False,
	):
		"""Calls a delayed task 'sendmail' that enqueus email in Email Queue queue

		:param print_html: Send given value as HTML attachment
		:param print_format: Attach print format of parent document
		:param attachments: A list of filenames that should be attached when sending this email
		:param recipients: Email recipients
		:param cc: Send email as CC to
		:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

		"""
		notify(
			self, print_html, print_format, attachments, recipients, cc, bcc, fetched_from_email_account
		)

	def _notify(
		self, print_html=None, print_format=None, attachments=None, recipients=None, cc=None, bcc=None
	):

		_notify(self, print_html, print_format, attachments, recipients, cc, bcc)

	def bot_reply(self):
		if self.comment_type == "Bot" and self.communication_type == "Chat":
			reply = BotReply().get_reply(self.content)
			if reply:
				frappe.get_doc(
					{
						"doctype": "Communication",
						"comment_type": "Bot",
						"communication_type": "Bot",
						"content": cstr(reply),
						"reference_doctype": self.reference_doctype,
						"reference_name": self.reference_name,
					}
				).insert()
				frappe.local.flags.commit = True

	def set_delivery_status(self, commit=False):
		"""Look into the status of Email Queue linked to this Communication and set the Delivery Status of this Communication"""
		delivery_status = None
		status_counts = Counter(
			frappe.db.sql_list("""select status from `tabEmail Queue` where communication=%s""", self.name)
		)
		if self.sent_or_received == "Received":
			return

		if status_counts.get("Not Sent") or status_counts.get("Sending"):
			delivery_status = "Sending"

		elif status_counts.get("Error"):
			delivery_status = "Error"

		elif status_counts.get("Expired"):
			delivery_status = "Expired"

		elif status_counts.get("Sent"):
			delivery_status = "Sent"

		if delivery_status:
			self.db_set("delivery_status", delivery_status)
			self.notify_change("update")

			# for list views and forms
			self.notify_update()

			if commit:
				frappe.db.commit()

	def parse_email_for_timeline_links(self):
		parse_email(self, [self.recipients, self.cc, self.bcc])

	# Timeline Links
	def set_timeline_links(self):
		contacts = []
		create_contact_enabled = self.email_account and frappe.db.get_value(
			"Email Account", self.email_account, "create_contact"
		)
		contacts = get_contacts(
			[self.sender, self.recipients, self.cc, self.bcc], auto_create_contact=create_contact_enabled
		)

		for contact_name in contacts:
			self.add_link("Contact", contact_name)

			# link contact's dynamic links to communication
			add_contact_links_to_communication(self, contact_name)

	def deduplicate_timeline_links(self):
		if self.timeline_links:
			links, duplicate = [], False

			for l in self.timeline_links:
				t = (l.link_doctype, l.link_name)
				if not t in links:
					links.append(t)
				else:
					duplicate = True

			if duplicate:
				del self.timeline_links[:]  # make it python 2 compatible as list.clear() is python 3 only
				for l in links:
					self.add_link(link_doctype=l[0], link_name=l[1])

	def add_link(self, link_doctype, link_name, autosave=False):
		self.append("timeline_links", {"link_doctype": link_doctype, "link_name": link_name})

		if autosave:
			self.save(ignore_permissions=True)

	def get_links(self):
		return self.timeline_links

	def remove_link(self, link_doctype, link_name, autosave=False, ignore_permissions=True):
		for l in self.timeline_links:
			if l.link_doctype == link_doctype and l.link_name == link_name:
				self.timeline_links.remove(l)

		if autosave:
			self.save(ignore_permissions=ignore_permissions)


def on_doctype_update():
	"""Add indexes in `tabCommunication`"""
	frappe.db.add_index("Communication", ["reference_doctype", "reference_name"])
	frappe.db.add_index("Communication", ["status", "communication_type"])


def has_permission(doc, ptype, user):
	if ptype == "read":
		if doc.reference_doctype == "Communication" and doc.reference_name == doc.name:
			return

		if doc.reference_doctype and doc.reference_name:
			if frappe.has_permission(doc.reference_doctype, ptype="read", doc=doc.reference_name):
				return True


def get_permission_query_conditions_for_communication(user):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if "Super Email User" in roles or "System Manager" in roles:
		return None
	else:
		accounts = frappe.get_all(
			"User Email", filters={"parent": user}, fields=["email_account"], distinct=True, order_by="idx"
		)

		if not accounts:
			return """`tabCommunication`.communication_medium!='Email'"""

		email_accounts = ['"%s"' % account.get("email_account") for account in accounts]
		return """`tabCommunication`.email_account in ({email_accounts})""".format(
			email_accounts=",".join(email_accounts)
		)


def get_contacts(email_strings: List[str], auto_create_contact=False) -> List[str]:
	email_addrs = get_emails(email_strings)
	contacts = []
	for email in email_addrs:
		email = get_email_without_link(email)
		contact_name = get_contact_name(email)

		if not contact_name and email and auto_create_contact:
			email_parts = email.split("@")
			first_name = frappe.unscrub(email_parts[0])

			try:
				contact_name = (
					"{0}-{1}".format(first_name, email_parts[1]) if first_name == "Contact" else first_name
				)
				contact = frappe.get_doc(
					{"doctype": "Contact", "first_name": contact_name, "name": contact_name}
				)
				contact.add_email(email_id=email, is_primary=True)
				contact.insert(ignore_permissions=True)
				contact_name = contact.name
			except Exception:
				traceback = frappe.get_traceback()
				frappe.log_error(traceback)

		if contact_name:
			contacts.append(contact_name)

	return contacts


def get_emails(email_strings: List[str]) -> List[str]:
	email_addrs = []

	for email_string in email_strings:
		if email_string:
			result = getaddresses([email_string])
			for email in result:
				email_addrs.append(email[1])

	return email_addrs


def add_contact_links_to_communication(communication, contact_name):
	contact_links = frappe.get_list(
		"Dynamic Link",
		filters={"parenttype": "Contact", "parent": contact_name},
		fields=["link_doctype", "link_name"],
	)

	if contact_links:
		for contact_link in contact_links:
			communication.add_link(contact_link.link_doctype, contact_link.link_name)


def parse_email(communication, email_strings):
	"""
	Parse email to add timeline links.
	When automatic email linking is enabled, an email from email_strings can contain
	a doctype and docname ie in the format `admin+doctype+docname@example.com`,
	the email is parsed and doctype and docname is extracted and timeline link is added.
	"""
	if not frappe.get_all("Email Account", filters={"enable_automatic_linking": 1}):
		return

	delimiter = "+"

	for email_string in email_strings:
		if email_string:
			for email in email_string.split(","):
				if delimiter in email:
					email = email.split("@")[0]
					email_local_parts = email.split(delimiter)
					if not len(email_local_parts) == 3:
						continue

					doctype = unquote(email_local_parts[1])
					docname = unquote(email_local_parts[2])

					if doctype and docname and frappe.db.exists(doctype, docname):
						communication.add_link(doctype, docname)


def get_email_without_link(email):
	"""
	returns email address without doctype links
	returns admin@example.com for email admin+doctype+docname@example.com
	"""
	if not frappe.get_all("Email Account", filters={"enable_automatic_linking": 1}):
		return email

	try:
		_email = email.split("@")
		email_id = _email[0].split("+")[0]
		email_host = _email[1]
	except IndexError:
		return email

	return "{0}@{1}".format(email_id, email_host)


def update_parent_document_on_communication(doc):
	"""Update mins_to_first_communication of parent document based on who is replying."""

	parent = get_parent_doc(doc)
	if not parent:
		return

	# update parent mins_to_first_communication only if we create the Email communication
	# ignore in case of only Comment is added
	if doc.communication_type == "Comment":
		return

	status_field = parent.meta.get_field("status")
	if status_field:
		options = (status_field.options or "").splitlines()

		# if status has a "Replied" option, then update the status for received communication
		if ("Replied" in options) and doc.sent_or_received == "Received":
			parent.db_set("status", "Open")
			parent.run_method("handle_hold_time", "Replied")
			apply_assignment_rule(parent)
		else:
			# update the modified date for document
			parent.update_modified()

	update_first_response_time(parent, doc)
	set_avg_response_time(parent, doc)
	parent.run_method("notify_communication", doc)
	parent.notify_update()


def update_first_response_time(parent, communication):
	if parent.meta.has_field("first_response_time") and not parent.get("first_response_time"):
		if is_system_user(communication.sender):
			if communication.sent_or_received == "Sent":
				first_responded_on = communication.creation
				if parent.meta.has_field("first_responded_on"):
					parent.db_set("first_responded_on", first_responded_on)
				first_response_time = round(time_diff_in_seconds(first_responded_on, parent.creation), 2)
				parent.db_set("first_response_time", first_response_time)


def set_avg_response_time(parent, communication):
	if parent.meta.has_field("avg_response_time") and communication.sent_or_received == "Sent":
		# avg response time for all the responses
		communications = frappe.get_list(
			"Communication",
			filters={"reference_doctype": parent.doctype, "reference_name": parent.name},
			fields=["sent_or_received", "name", "creation"],
			order_by="creation",
		)

		if len(communications):
			response_times = []
			for i in range(len(communications)):
				if (
					communications[i].sent_or_received == "Sent"
					and communications[i - 1].sent_or_received == "Received"
				):
					response_time = round(
						time_diff_in_seconds(communications[i].creation, communications[i - 1].creation), 2
					)
					if response_time > 0:
						response_times.append(response_time)
			if response_times:
				avg_response_time = sum(response_times) / len(response_times)
				parent.db_set("avg_response_time", avg_response_time)
