# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.database.schema import add_column
from frappe.desk.notifications import notify_mentions
from frappe.exceptions import ImplicitCommitError
from frappe.model.document import Document
from frappe.model.utils import is_virtual_doctype
from frappe.website.utils import clear_cache


class Comment(Document):
	def after_insert(self):
		notify_mentions(self.reference_doctype, self.reference_name, self.content)
		self.notify_change("add")

	def validate(self):
		if not self.comment_email:
			self.comment_email = frappe.session.user
		self.content = frappe.utils.sanitize_html(self.content)

	def on_update(self):
		update_comment_in_doc(self)
		if self.is_new():
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
		if frappe.db.is_column_missing(e) and getattr(frappe.local, "request", None):
			# missing column and in request, add column and update after commit
			frappe.local._comments = getattr(frappe.local, "_comments", []) + [
				(reference_doctype, reference_name, _comments)
			]

		elif frappe.db.is_data_too_long(e):
			raise frappe.DataTooLongException

		else:
			raise ImplicitCommitError
	else:
		if frappe.flags.in_patch:
			return

		# Clear route cache
		if route := frappe.get_cached_value(reference_doctype, reference_name, "route"):
			clear_cache(route)


def update_comments_in_parent_after_request():
	"""update _comments in parent if _comments column is missing"""
	if hasattr(frappe.local, "_comments"):
		for (reference_doctype, reference_name, _comments) in frappe.local._comments:
			add_column(reference_doctype, "_comments", "Text")
			update_comments_in_parent(reference_doctype, reference_name, _comments)

		frappe.db.commit()
