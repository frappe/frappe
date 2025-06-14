# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from collections import Counter
from email.utils import getaddresses
from urllib.parse import unquote_plus

from bs4 import BeautifulSoup

import frappe
from frappe import _
from frappe.automation.doctype.assignment_rule.assignment_rule import (
	apply as apply_assignment_rule,
)
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.core.doctype.comment.comment import update_comment_in_doc
from frappe.core.doctype.communication.email import validate_email
from frappe.core.doctype.communication.mixins import CommunicationEmailMixin
from frappe.core.utils import get_parent_doc
from frappe.model.document import Document
from frappe.utils import (
	cstr,
	parse_addr,
	split_emails,
	strip_html,
	time_diff_in_seconds,
	validate_email_address,
)
from frappe.utils.user import is_system_user

exclude_from_linked_with = True


class Communication(Document, CommunicationEmailMixin):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.communication_link.communication_link import CommunicationLink
		from frappe.types import DF

		_user_tags: DF.Data | None
		bcc: DF.Code | None
		cc: DF.Code | None
		communication_date: DF.Datetime | None
		communication_medium: DF.Literal[
			"", "Email", "Chat", "Phone", "SMS", "Event", "Meeting", "Visit", "Other"
		]
		communication_type: DF.Literal["Communication", "Automated Message"]
		content: DF.TextEditor | None
		delivery_status: DF.Literal[
			"",
			"Sent",
			"Bounced",
			"Opened",
			"Marked As Spam",
			"Rejected",
			"Delayed",
			"Soft-Bounced",
			"Clicked",
			"Recipient Unsubscribed",
			"Error",
			"Expired",
			"Sending",
			"Read",
			"Scheduled",
		]
		email_account: DF.Link | None
		email_status: DF.Literal["Open", "Spam", "Trash"]
		email_template: DF.Link | None
		has_attachment: DF.Check
		imap_folder: DF.Data | None
		in_reply_to: DF.Link | None
		message_id: DF.SmallText | None
		phone_no: DF.Data | None
		read_by_recipient: DF.Check
		read_by_recipient_on: DF.Datetime | None
		read_receipt: DF.Check
		recipients: DF.Code | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		reference_owner: DF.ReadOnly | None
		seen: DF.Check
		send_after: DF.Datetime | None
		sender: DF.Data | None
		sender_full_name: DF.Data | None
		sent_or_received: DF.Literal["Sent", "Received"]
		status: DF.Literal["Open", "Replied", "Closed", "Linked"]
		subject: DF.SmallText
		text_content: DF.Code | None
		timeline_links: DF.Table[CommunicationLink]
		uid: DF.Int
		unread_notification_sent: DF.Check
		user: DF.Link | None
	# end: auto-generated types

	"""Communication represents an external communication like Email."""

	no_feed_on_delete = True
	DOCTYPE = "Communication"

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

		if not self.send_after:  # Handle empty string, always set NULL
			self.send_after = None

		validate_email(self)

		if self.communication_medium == "Email":
			self.parse_email_for_timeline_links()
			self.set_timeline_links()
			self.deduplicate_timeline_links()

		self.set_sender_full_name()

		if self.is_new():
			self.set_status()
			self.mark_email_as_spam()

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

		self.notify_change("add")

	def set_signature_in_email_content(self):
		"""Set sender's User.email_signature or default outgoing's EmailAccount.signature to the email"""
		if not self.content:
			return

		soup = BeautifulSoup(self.content, "html.parser")
		email_body = soup.find("div", {"class": "ql-editor read-mode"})

		if not email_body:
			return

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

		soup = BeautifulSoup(signature, "html.parser")
		html_signature = soup.find("div", {"class": "ql-editor read-mode"})
		_signature = None
		if html_signature:
			_signature = html_signature.renderContents()

		if (cstr(_signature) or signature) not in self.content:
			self.content = f'{self.content}</p><br><p class="signature">{signature}'

	def before_save(self):
		if not self.flags.skip_add_signature:
			self.set_signature_in_email_content()

	def on_update(self):
		# add to _comment property of the doctype, so it shows up in
		# comments count for the list view
		update_comment_in_doc(self)

		parent = get_parent_doc(self)
		if (method := getattr(parent, "on_communication_update", None)) and callable(method):
			parent.on_communication_update(self)
			return
		update_parent_document_on_communication(self)

	def on_trash(self):
		self.notify_change("delete")

	@property
	def sender_mailid(self):
		return parse_addr(self.sender)[1] if self.sender else ""

	@staticmethod
	def _get_emails_list(emails=None, exclude_displayname=False):
		"""Return list of emails from given email string.

		* Removes duplicate mailids
		* Removes display name from email address if exclude_displayname is True
		"""
		emails = split_emails(emails) if isinstance(emails, str) else (emails or [])
		if exclude_displayname:
			return [email.lower() for email in {parse_addr(email)[1] for email in emails} if email]
		return [email for email in set(emails) if email]

	def to_list(self, exclude_displayname=True):
		"""Return `to` list."""
		return self._get_emails_list(self.recipients, exclude_displayname=exclude_displayname)

	def cc_list(self, exclude_displayname=True):
		"""Return `cc` list."""
		return self._get_emails_list(self.cc, exclude_displayname=exclude_displayname)

	def bcc_list(self, exclude_displayname=True):
		"""Return `bcc` list."""
		return self._get_emails_list(self.bcc, exclude_displayname=exclude_displayname)

	def get_attachments(self):
		return frappe.get_all(
			"File",
			fields=["name", "file_name", "file_url", "is_private"],
			filters={
				"attached_to_name": self.name,
				"attached_to_doctype": self.DOCTYPE,
			},
		)

	def notify_change(self, action):
		frappe.publish_realtime(
			"docinfo_update",
			{"doc": self.as_dict(), "key": "communications", "action": action},
			doctype=self.reference_doctype,
			docname=self.reference_name,
			after_commit=True,
		)

	def set_status(self):
		if self.reference_doctype and self.reference_name:
			self.status = "Linked"
		else:
			self.status = "Open"

		if self.send_after and self.is_new():
			self.delivery_status = "Scheduled"

	def mark_email_as_spam(self):
		if (
			self.communication_type == "Communication"
			and self.communication_medium == "Email"
			and self.sent_or_received == "Received"
			and frappe.db.exists("Email Rule", {"email_id": self.sender, "is_spam": 1})
		):
			self.email_status = "Spam"

	@classmethod
	def find(cls, name, ignore_error=False):
		try:
			return frappe.get_doc(cls.DOCTYPE, name)
		except frappe.DoesNotExistError:
			if ignore_error:
				return
			raise

	@classmethod
	def find_one_by_filters(cls, *, order_by=None, **kwargs):
		name = frappe.db.get_value(cls.DOCTYPE, kwargs, order_by=order_by)
		return cls.find(name) if name else None

	def update_db(self, **kwargs):
		frappe.db.set_value(self.DOCTYPE, self.name, kwargs)

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

	def set_delivery_status(self, commit=False):
		"""Look into the status of Email Queue linked to this Communication and set the Delivery Status of this Communication"""
		delivery_status = None
		status_counts = Counter(
			frappe.get_all("Email Queue", pluck="status", filters={"communication": self.name})
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
		if not frappe.db.get_value("Email Account", filters={"enable_automatic_linking": 1}):
			return

		for doctype, docname in parse_email([self.recipients, self.cc, self.bcc]):
			if not frappe.db.get_value(doctype, docname, ignore=True):
				continue

			self.add_link(doctype, docname)

			if not self.reference_doctype:
				self.reference_doctype = doctype
				self.reference_name = docname

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
		if not self.timeline_links:
			return

		unique_links = {(link.link_doctype, link.link_name) for link in self.timeline_links}
		self.timeline_links = []
		for doctype, name in unique_links:
			self.add_link(doctype, name)

	def add_link(self, link_doctype, link_name, autosave=False):
		self.append("timeline_links", {"link_doctype": link_doctype, "link_name": link_name})

		if autosave:
			self.save(ignore_permissions=True)

	def get_links(self):
		return self.timeline_links

	def remove_link(self, link_doctype, link_name, autosave=False, ignore_permissions=True):
		for l in list(self.timeline_links):
			if l.link_doctype == link_doctype and l.link_name == link_name:
				self.timeline_links.remove(l)

		if autosave:
			self.save(ignore_permissions=ignore_permissions)


def on_doctype_update():
	"""Add indexes in `tabCommunication`"""
	frappe.db.add_index("Communication", ["reference_doctype", "reference_name"])
	frappe.db.add_index("Communication", ["status", "communication_type"])
	frappe.db.add_index("Communication", ["message_id(140)"])


def has_permission(doc, ptype, user=None, debug=False):
	if ptype == "read":
		if doc.reference_doctype == "Communication" and doc.reference_name == doc.name:
			return True

		if doc.reference_doctype and doc.reference_name:
			return frappe.has_permission(
				doc.reference_doctype, ptype="read", doc=doc.reference_name, user=user, debug=debug
			)

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

		email_accounts = ['"{}"'.format(account.get("email_account")) for account in accounts]
		return """`tabCommunication`.email_account in ({email_accounts}) or `tabCommunication`.recipients LIKE '%{user}%' or `tabCommunication`.sender LIKE '%{user}%' or `tabCommunication`.cc LIKE '%{user}%' or `tabCommunication`.bcc LIKE '%{user}%'""".format(
			email_accounts=",".join(email_accounts), user=user
		)


def get_contacts(email_strings: list[str], auto_create_contact=False) -> list[str]:
	email_addrs = get_emails(email_strings)
	contacts = []
	for email in email_addrs:
		email = get_email_without_link(email)
		contact_name = get_contact_name(email)

		if not contact_name and email and auto_create_contact:
			email_parts = email.split("@")
			first_name = frappe.unscrub(email_parts[0])

			try:
				contact_name = f"{first_name}-{email_parts[1]}" if first_name == "Contact" else first_name
				contact = frappe.get_doc(
					{"doctype": "Contact", "first_name": contact_name, "name": contact_name}
				)
				contact.add_email(email_id=email, is_primary=True)
				contact.insert(ignore_permissions=True)
				contact_name = contact.name
			except Exception:
				contact_name = None
				contact.log_error("Unable to add contact")

		if contact_name:
			contacts.append(contact_name)

	return contacts


def get_emails(email_strings: list[str]) -> list[str]:
	email_addrs = []

	for email_string in email_strings:
		if email_string:
			result = getaddresses([email_string])
			email_addrs.extend(email[1] for email in result)
	return email_addrs


def add_contact_links_to_communication(communication, contact_name):
	contact_links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "parent": contact_name},
		fields=["link_doctype", "link_name"],
	)

	if contact_links:
		for contact_link in contact_links:
			communication.add_link(contact_link.link_doctype, contact_link.link_name)


def parse_email(email_strings):
	"""
	Parse email to add timeline links.
	When automatic email linking is enabled, an email from email_strings can contain
	a doctype and docname ie in the format `admin+doctype+docname@example.com` or `admin+doctype=docname@example.com`,
	the email is parsed and doctype and docname is extracted.

	see: RFC5233
	"""
	for email_string in email_strings:
		if not email_string:
			continue

		for email in email_string.split(","):
			local_part = email.split("@", 1)[0].strip('"')
			user, detail = None, None
			if "+" in local_part:
				user, detail = local_part.split("+", 1)
			elif "--" in local_part:
				detail, user = local_part.rsplit("--", 1)

			if not detail:
				continue

			document_parts = None
			if "=" in detail:
				document_parts = detail.split("=", 1)
			elif "+" in detail:
				document_parts = detail.split("+", 1)

			if not document_parts or len(document_parts) != 2:
				continue

			doctype = unquote_plus(document_parts[0])
			docname = unquote_plus(document_parts[1])
			yield doctype, docname


def get_email_without_link(email):
	"""Return email address without doctype links.

	e.g. 'admin@example.com' is returned for email 'admin+doctype+docname@example.com'

	see: RFC5233
	"""
	if not frappe.get_all("Email Account", filters={"enable_automatic_linking": 1}):
		return email

	try:
		_email = email.split("@")
		_local_part = _email[0].strip('"')
		if "+" in _local_part:
			user = _local_part.split("+", 1)[0]
		elif "--" in _local_part:
			user = _local_part.split("--", 1)[1]
		else:
			user = _local_part
		domain = _email[1]
	except IndexError:
		return email

	return f"{user}@{domain}"


def update_parent_document_on_communication(doc):
	"""Update mins_to_first_communication of parent document based on who is replying."""

	parent = get_parent_doc(doc)
	if not parent:
		return

	status_field = parent.meta.get_field("status")
	if status_field:
		options = (status_field.options or "").splitlines()

		# if status has a "Open" option and status is "Replied", then update the status for received communication
		if (
			(("Open" in options) and parent.status == "Replied" and doc.sent_or_received == "Received")
			or (
				parent.doctype == "Issue" and ("Open" in options) and doc.sent_or_received == "Received"
			)  # For 'Issue', current status is not considered.
		):
			parent.db_set("status", "Open")
			parent.run_method("handle_hold_time", "Replied")
			apply_assignment_rule(parent)

	update_first_response_time(parent, doc)
	set_avg_response_time(parent, doc)
	parent.run_method("notify_communication", doc)
	parent.notify_update()


def update_first_response_time(parent, communication):
	if parent.meta.has_field("first_response_time") and not parent.get("first_response_time"):
		if (
			is_system_user(communication.sender)
			or frappe.get_cached_value("User", frappe.session.user, "user_type") == "System User"
		):
			if (
				communication.sent_or_received == "Sent"
				and communication.communication_type == "Communication"
			):
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
