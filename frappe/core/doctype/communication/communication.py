# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, absolute_import
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, get_fullname, strip_html, cstr
from frappe.core.doctype.communication.comment import (notify_mentions,
	update_comment_in_doc, on_trash)
from frappe.core.doctype.communication.email import (validate_email,
	notify, _notify, update_parent_status)
from frappe.utils.bot import BotReply
from frappe.utils import parse_addr

from collections import Counter

exclude_from_linked_with = True

class Communication(Document):
	no_feed_on_delete = True

	"""Communication represents an external communication like Email."""
	def onload(self):
		"""create email flag queue"""
		if self.communication_type == "Communication" and self.communication_medium == "Email" \
			and self.sent_or_received == "Received" and self.uid and self.uid != -1:

			email_flag_queue = frappe.db.get_value("Email Flag Queue", {
				"communication": self.name,
				"is_completed": 0})
			if email_flag_queue:
				return

			frappe.get_doc({
				"doctype": "Email Flag Queue",
				"action": "Read",
				"communication": self.name,
				"uid": self.uid,
				"email_account": self.email_account
			}).insert(ignore_permissions=True)
			frappe.db.commit()

	def validate(self):
		if self.reference_doctype and self.reference_name:
			if not self.reference_owner:
				self.reference_owner = frappe.db.get_value(self.reference_doctype, self.reference_name, "owner")

			# prevent communication against a child table
			if frappe.get_meta(self.reference_doctype).istable:
				frappe.throw(_("Cannot create a {0} against a child document: {1}")
					.format(_(self.communication_type), _(self.reference_doctype)))

		if not self.user:
			self.user = frappe.session.user

		if not self.subject:
			self.subject = strip_html((self.content or "")[:141])

		if not self.sent_or_received:
			self.seen = 1
			self.sent_or_received = "Sent"

		self.set_status()
		self.set_sender_full_name()
		validate_email(self)
		self.set_timeline_doc()

	def after_insert(self):
		if not (self.reference_doctype and self.reference_name):
			return

		if self.reference_doctype == "Communication" and self.sent_or_received == "Sent":
			frappe.db.set_value("Communication", self.reference_name, "status", "Replied")

		if self.communication_type in ("Communication", "Comment"):
			# send new comment to listening clients
			frappe.publish_realtime('new_communication', self.as_dict(),
			    doctype=self.reference_doctype, docname=self.reference_name,
			    after_commit=True)

			if self.communication_type == "Comment":
				notify_mentions(self)

		elif self.communication_type in ("Chat", "Notification", "Bot"):
			if self.reference_name == frappe.session.user:
				message = self.as_dict()
				message['broadcast'] = True
				frappe.publish_realtime('new_message', message, after_commit=True)
			else:
				# reference_name contains the user who is addressed in the messages' page comment
				frappe.publish_realtime('new_message', self.as_dict(),
				    user=self.reference_name, after_commit=True)

	def on_update(self):
		"""Update parent status as `Open` or `Replied`."""
		if self.comment_type != 'Updated':
			update_parent_status(self)
			update_comment_in_doc(self)
			self.bot_reply()

	def on_trash(self):
		if (not self.flags.ignore_permissions
			and self.communication_type=="Comment" and self.comment_type != "Comment"):

			# prevent deletion of auto-created comments if not ignore_permissions
			frappe.throw(_("Sorry! You cannot delete auto-generated comments"))

		if self.communication_type in ("Communication", "Comment"):
			# send delete comment to listening clients
			frappe.publish_realtime('delete_communication', self.as_dict(),
				doctype= self.reference_doctype, docname = self.reference_name,
				after_commit=True)
			# delete the comments from _comment
			on_trash(self)

	def set_status(self):
		if not self.is_new():
			return

		if self.reference_doctype and self.reference_name:
			self.status = "Linked"
		elif self.communication_type=="Communication":
			self.status = "Open"
		else:
			self.status = "Closed"

		# set email status to spam
		email_rule = frappe.db.get_value("Email Rule", { "email_id": self.sender, "is_spam":1 })
		if self.communication_type == "Communication" and self.communication_medium == "Email" \
			and self.sent_or_received == "Sent" and email_rule:

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
				if self.sent_or_received=='Sent':
					validate_email_add(self.sender, throw=True)
				sender_name, sender_email = parse_addr(self.sender)
				if sender_name == sender_email:
					sender_name = None
				self.sender = sender_email
				self.sender_full_name = sender_name or get_fullname(frappe.session.user) if frappe.session.user!='Administrator' else None

	def get_parent_doc(self):
		"""Returns document of `reference_doctype`, `reference_doctype`"""
		if not hasattr(self, "parent_doc"):
			if self.reference_doctype and self.reference_name:
				self.parent_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			else:
				self.parent_doc = None
		return self.parent_doc

	def set_timeline_doc(self):
		"""Set timeline_doctype and timeline_name"""
		parent_doc = self.get_parent_doc()
		if (self.timeline_doctype and self.timeline_name) or not parent_doc:
			return

		timeline_field = parent_doc.meta.timeline_field
		if not timeline_field:
			return

		doctype = parent_doc.meta.get_link_doctype(timeline_field)
		name = parent_doc.get(timeline_field)

		if doctype and name:
			self.timeline_doctype = doctype
			self.timeline_name = name

		else:
			return

	def send(self, print_html=None, print_format=None, attachments=None,
		send_me_a_copy=False, recipients=None):
		"""Send communication via Email.

		:param print_html: Send given value as HTML attachment.
		:param print_format: Attach print format of parent document."""

		self.send_me_a_copy = send_me_a_copy
		self.notify(print_html, print_format, attachments, recipients)

	def notify(self, print_html=None, print_format=None, attachments=None,
		recipients=None, cc=None, fetched_from_email_account=False):
		"""Calls a delayed task 'sendmail' that enqueus email in Email Queue queue

		:param print_html: Send given value as HTML attachment
		:param print_format: Attach print format of parent document
		:param attachments: A list of filenames that should be attached when sending this email
		:param recipients: Email recipients
		:param cc: Send email as CC to
		:param fetched_from_email_account: True when pulling email, the notification shouldn't go to the main recipient

		"""
		notify(self, print_html, print_format, attachments, recipients, cc,
			fetched_from_email_account)

	def _notify(self, print_html=None, print_format=None, attachments=None,
		recipients=None, cc=None):

		_notify(self, print_html, print_format, attachments, recipients, cc)

	def bot_reply(self):
		if self.comment_type == 'Bot' and self.communication_type == 'Chat':
			reply = BotReply().get_reply(self.content)
			if reply:
				frappe.get_doc({
					"doctype": "Communication",
					"comment_type": "Bot",
					"communication_type": "Bot",
					"content": cstr(reply),
					"reference_doctype": self.reference_doctype,
					"reference_name": self.reference_name
				}).insert()
				frappe.local.flags.commit = True

	def set_delivery_status(self, commit=False):
		'''Look into the status of Email Queue linked to this Communication and set the Delivery Status of this Communication'''
		delivery_status = None
		status_counts = Counter(frappe.db.sql_list('''select status from `tabEmail Queue` where communication=%s''', self.name))
		if self.sent_or_received == "Received":
			return

		if status_counts.get('Not Sent') or status_counts.get('Sending'):
			delivery_status = 'Sending'

		elif status_counts.get('Error'):
			delivery_status = 'Error'

		elif status_counts.get('Expired'):
			delivery_status = 'Expired'

		elif status_counts.get('Sent'):
			delivery_status = 'Sent'

		if delivery_status:
			self.db_set('delivery_status', delivery_status)

			frappe.publish_realtime('update_communication', self.as_dict(),
				doctype=self.reference_doctype, docname=self.reference_name, after_commit=True)

			# for list views and forms
			self.notify_update()

			if commit:
				frappe.db.commit()

def on_doctype_update():
	"""Add indexes in `tabCommunication`"""
	frappe.db.add_index("Communication", ["reference_doctype", "reference_name"])
	frappe.db.add_index("Communication", ["timeline_doctype", "timeline_name"])
	frappe.db.add_index("Communication", ["link_doctype", "link_name"])
	frappe.db.add_index("Communication", ["status", "communication_type"])

def has_permission(doc, ptype, user):
	if ptype=="read":
		if (doc.reference_doctype == "Communication" and doc.reference_name == doc.name) \
			or (doc.timeline_doctype == "Communication" and doc.timeline_name == doc.name):
				return

		if doc.reference_doctype and doc.reference_name:
			if frappe.has_permission(doc.reference_doctype, ptype="read", doc=doc.reference_name):
				return True
		if doc.timeline_doctype and doc.timeline_name:
			if frappe.has_permission(doc.timeline_doctype, ptype="read", doc=doc.timeline_name):
				return True

def get_permission_query_conditions_for_communication(user):
	from frappe.email.inbox import get_email_accounts

	if not user: user = frappe.session.user

	roles = frappe.get_roles(user)

	if "Super Email User" in roles or "System Manager" in roles:
		return None
	else:
		accounts = frappe.get_all("User Email", filters={ "parent": user },
			fields=["email_account"],
			distinct=True, order_by="idx")

		if not accounts:
			return """tabCommunication.communication_medium!='Email'"""

		email_accounts = [ '"%s"'%account.get("email_account") for account in accounts ]
		return """tabCommunication.email_account in ({email_accounts})"""\
			.format(email_accounts=','.join(email_accounts))