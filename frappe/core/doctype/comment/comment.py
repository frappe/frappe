# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE
import json

from akismet import CheckResponse, Config, SyncClient

import frappe
from frappe.database.schema import add_column
from frappe.desk.notifications import notify_mentions
from frappe.exceptions import ImplicitCommitError
from frappe.model.document import Document
from frappe.model.utils import is_virtual_doctype
from frappe.website.utils import clear_cache

status_map = {
	CheckResponse.DISCARD: "Discard",
	CheckResponse.SPAM: "Spam",
	CheckResponse.HAM: "Ham",
}


class Comment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		comment_by: DF.Data | None
		comment_email: DF.Data | None
		comment_type: DF.Literal[
			"Comment",
			"Like",
			"Info",
			"Label",
			"Workflow",
			"Created",
			"Submitted",
			"Cancelled",
			"Updated",
			"Deleted",
			"Assigned",
			"Assignment Completed",
			"Attachment",
			"Attachment Removed",
			"Shared",
			"Unshared",
			"Bot",
			"Relinked",
			"Edit",
		]
		content: DF.HTMLEditor | None
		ip_address: DF.Data | None
		published: DF.Check
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		reference_owner: DF.Data | None
		seen: DF.Check
		spam_type: DF.Literal["", "Review Pending", "Spam", "Ham", "Discard"]
		subject: DF.Text | None
	# end: auto-generated types

	no_feed_on_delete = True

	def after_insert(self):
		result = self.delete_if_spam()
		if result:
			self.notify_change("delete")
		notify_mentions(self.reference_doctype, self.reference_name, self.content)
		self.notify_change("add")

	def before_validate(self):
		if not self.ip_address:
			self.ip_address = frappe.local.request_ip

	def validate(self):
		if not self.comment_email:
			self.comment_email = frappe.session.user
		self.content = frappe.utils.sanitize_html(self.content, always_sanitize=True)
		self.validate_spam()

	def on_update(self):
		update_comment_in_doc(self)
		result = self.delete_if_spam()
		if result:
			self.notify_change("delete")
		if not self.is_new():
			self.notify_change("update")

	def on_trash(self):
		self.remove_comment_from_cache()
		self.notify_change("delete")

	def notify_change(self, action):
		key_map = {
			"Like": "like_logs",
			"Assigned": "assignment_logs",
			"Assignment Completed": "assignment_logs",
			"Comment": "comments",
			"Attachment": "attachment_logs",
			"Attachment Removed": "attachment_logs",
		}
		key = key_map.get(self.comment_type)
		if not key:
			return

		frappe.publish_realtime(
			"docinfo_update",
			{"doc": self.as_dict(), "key": key, "action": action},
			doctype=self.reference_doctype,
			docname=self.reference_name,
			after_commit=True,
		)

	def remove_comment_from_cache(self):
		_comments = get_comments_from_parent(self)
		for c in list(_comments):
			if c.get("name") == self.name:
				_comments.remove(c)

		update_comments_in_parent(self.reference_doctype, self.reference_name, _comments)

	def validate_spam(self):
		from bs4 import BeautifulSoup

		spam_filtering = frappe.db.get_single_value("Akismet Settings", "spam_filtering")
		if self.comment_type != "Comment":
			return

		comment = BeautifulSoup(self.content, "html.parser").get_text()
		if not comment:
			return
		akismet_client = get_akismet()

		if not akismet_client:
			return

		result = akismet_client.comment_check(
			user_ip=self.ip_address,
			comment_type="comment",
			comment_content=comment,
			comment_author=self.comment_by,
			comment_author_email=self.comment_email,
		)

		self.spam_type = status_map.get(result, "Review Pending")

		if (
			result in [CheckResponse.DISCARD, CheckResponse.SPAM]
			and spam_filtering == "Keep spam comment for review"
		):
			self.spam_type = "Review Pending"

	def delete_if_spam(self):
		akismet_setting = frappe.get_single("Akismet Settings")
		if (
			self.comment_type == "Comment"
			and akismet_setting.enable
			and akismet_setting.spam_filtering == "Silently discard spam comment"
			and self.spam_type in ["Spam", "Discard"]
		):
			self.delete()
			return True
		return False


@frappe.whitelist()
def mark_as_spam_or_ham(comment, type):
	frappe.only_for(["System Manager"])
	# Can't do doc.save(), since it will be marked pending for review
	# if spam_filtering is set to "Keep spam comment for review"
	frappe.db.set_value("Comment", comment, "spam_type", type)
	doc = frappe.get_doc("Comment", comment, for_update=False)

	akismet_client = get_akismet()
	if not akismet_client:
		return

	if type == "Spam":
		akismet_client.submit_spam(
			comment_type="comment",
			comment_author=doc.comment_by,
			comment_author_email=doc.comment_email,
			comment_content=doc.content,
			user_ip=doc.ip_address,
		)
	else:
		akismet_client.submit_ham(
			comment_type="comment",
			comment_author=doc.comment_by,
			comment_author_email=doc.comment_email,
			comment_content=doc.content,
			user_ip=doc.ip_address,
		)
	doc.notify_change("update")


def get_akismet() -> SyncClient | None:
	akismet_setting = frappe.get_single("Akismet Settings")
	if not akismet_setting.enable:
		return None

	config = Config(key=akismet_setting.get_password("api_key"), url=frappe.local.site)
	akismet_client = SyncClient.validated_client(config=config)
	akismet_client._http_client.timeout = akismet_setting.timeout or 5
	return akismet_client


def on_doctype_update():
	frappe.db.add_index("Comment", ["reference_doctype", "reference_name"])


def update_comment_in_doc(doc):
	"""Updates `_comments` (JSON) property in parent Document.
	Creates a column `_comments` if property does not exist.

	Only user created Communication or Comment of type Comment are saved.

	`_comments` format

			{
					"comment": [String],
					"by": [user],
					"name": [Comment Document name]
			}"""

	# only comments get updates, not likes, assignments etc.
	if doc.doctype == "Comment" and doc.comment_type != "Comment":
		return

	def get_truncated(content):
		return (content[:97] + "...") if len(content) > 100 else content

	if doc.reference_doctype and doc.reference_name and doc.content:
		_comments = get_comments_from_parent(doc)

		updated = False
		for c in _comments:
			if c.get("name") == doc.name:
				c["comment"] = get_truncated(doc.content)
				updated = True

		if not updated:
			_comments.append(
				{
					"comment": get_truncated(doc.content),
					# "comment_email" for Comment and "sender" for Communication
					"by": getattr(doc, "comment_email", None) or getattr(doc, "sender", None) or doc.owner,
					"name": doc.name,
				}
			)

		update_comments_in_parent(doc.reference_doctype, doc.reference_name, _comments)


def get_comments_from_parent(doc):
	"""
	get the list of comments cached in the document record in the column
	`_comments`
	"""
	try:
		if is_virtual_doctype(doc.reference_doctype):
			_comments = "[]"
		else:
			_comments = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "_comments") or "[]"

	except Exception as e:
		if frappe.db.is_missing_table_or_column(e):
			_comments = "[]"

		else:
			raise

	try:
		return json.loads(_comments)
	except ValueError:
		return []


def update_comments_in_parent(reference_doctype, reference_name, _comments):
	"""Updates `_comments` property in parent Document with given dict.

	:param _comments: Dict of comments."""
	if (
		not reference_doctype
		or not reference_name
		or frappe.db.get_value("DocType", reference_doctype, "issingle")
		or is_virtual_doctype(reference_doctype)
	):
		return

	try:
		# use sql, so that we do not mess with the timestamp
		frappe.db.sql(
			f"""update `tab{reference_doctype}` set `_comments`=%s where name=%s""",  # nosec
			(json.dumps(_comments[-100:]), reference_name),
		)

	except Exception as e:
		if frappe.db.is_missing_column(e) and getattr(frappe.local, "request", None):
			pass
		elif frappe.db.is_data_too_long(e):
			raise frappe.DataTooLongException
		else:
			raise
	else:
		if frappe.flags.in_patch:
			return

		# Clear route cache
		if route := frappe.get_cached_value(reference_doctype, reference_name, "route"):
			clear_cache(route)
