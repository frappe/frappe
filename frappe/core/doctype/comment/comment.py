# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.website.render import clear_cache
from frappe.model.document import Document
from frappe.model.db_schema import add_column
from frappe.utils import get_fullname

exclude_from_linked_with = True

class Comment(Document):
	"""Comments are added to Documents via forms or views like blogs etc."""
	no_feed_on_delete = True

	def get_feed(self):
		"""Returns feed HTML from Comment."""
		if self.comment_doctype == "Message":
			return

		if self.comment_type in ("Created", "Submitted", "Cancelled", "Label"):
			comment_type = "Label"
		elif self.comment_type == "Comment":
			comment_type = "Comment"
		else:
			comment_type = "Info"

		return {
			"subject": self.comment,
			"doctype": self.comment_doctype,
			"name": self.comment_docname,
			"feed_type": comment_type
		}

	def after_insert(self):
		"""Send realtime updates"""
		if not self.comment_doctype:
			return
		if self.comment_doctype == 'Message':
			if self.comment_docname == frappe.session.user:
				message = self.as_dict()
				message['broadcast'] = True
				frappe.publish_realtime('new_message', message)
			else:
				# comment_docname contains the user who is addressed in the messages' page comment
				frappe.publish_realtime('new_message', self.as_dict(), user=self.comment_docname)
		else:
			frappe.publish_realtime('new_comment', self.as_dict(), doctype= self.comment_doctype,
				docname = self.comment_docname)

	def validate(self):
		"""Raise exception for more than 50 comments."""
		if frappe.db.sql("""select count(*) from tabComment where comment_doctype=%s
			and comment_docname=%s""", (self.doctype, self.name))[0][0] >= 50:
			frappe.throw(_("Cannot add more than 50 comments"))

		if not self.comment_by_fullname and self.comment_by:
			self.comment_by_fullname = get_fullname(self.comment_by)

	def on_update(self):
		"""Updates `_comments` property in parent Document."""
		self.update_comment_in_doc()

	def update_comment_in_doc(self):
		"""Updates `_comments` (JSON) property in parent Document.
		Creates a column `_comments` if property does not exist.

		`_comments` format

			{
				"comment": [String],
				"by": [user],
				"name": [Comment Document name]
			}"""
		if self.comment_doctype and self.comment_docname and self.comment and self.comment_type=="Comment":
			_comments = self.get_comments_from_parent()
			updated = False
			for c in _comments:
				if c.get("name")==self.name:
					c["comment"] = self.comment
					updated = True

			if not updated:
				_comments.append({
					"comment": self.comment,
					"by": self.comment_by or self.owner,
					"name":self.name
				})
			self.update_comments_in_parent(_comments)

	def get_comments_from_parent(self):
		try:
			_comments = frappe.db.get_value(self.comment_doctype,
				self.comment_docname, "_comments") or "[]"

			return json.loads(_comments)

		except Exception, e:

			if e.args[0]==1054:
				if frappe.flags.in_test:
					return

				add_column(self.comment_doctype, "_comments", "Text")

				return self.get_comments_from_parent()

			elif e.args[0]==1146:
				# no table
				pass

			else:
				raise

	def update_comments_in_parent(self, _comments):
		"""Updates `_comments` property in parent Document with given dict.

		:param _comments: Dict of comments."""
		if not self.comment_doctype or frappe.db.get_value("DocType", self.comment_doctype, "issingle"):
			return

		# use sql, so that we do not mess with the timestamp
		frappe.db.sql("""update `tab%s` set `_comments`=%s where name=%s""" % (self.comment_doctype,
			"%s", "%s"), (json.dumps(_comments), self.comment_docname))

		comment_doc = frappe.get_doc(self.comment_doctype, self.comment_docname)
		if getattr(comment_doc, "get_route", None):
			clear_cache(comment_doc.get_route())

	def on_trash(self):
		"""Removes from `_comments` in parent Document"""
		if self.comment_doctype == "Message":
			return

		if (self.comment_type or "Comment") != "Comment":
			frappe.only_for("System Manager")

		_comments = self.get_comments_from_parent()
		for c in _comments:
			if c.get("name")==self.name:
				_comments.remove(c)

		self.update_comments_in_parent(_comments)

def on_doctype_update():
	"""Add index to `tabComment` `(comment_doctype, comment_name)`"""
	if not frappe.db.sql("""show index from `tabComment`
		where Key_name="comment_doctype_docname_index" """):
		frappe.db.commit()
		frappe.db.sql("""alter table `tabComment`
			add index comment_doctype_docname_index(comment_doctype, comment_docname)""")
