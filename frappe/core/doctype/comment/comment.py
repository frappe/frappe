# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.website.render import clear_cache
from frappe.model.document import Document
from frappe.model.db_schema import add_column

class Comment(Document):

	def validate(self):
		if frappe.db.sql("""select count(*) from tabComment where comment_doctype=%s
			and comment_docname=%s""", (self.doctype, self.name))[0][0] >= 50:
			frappe.throw(_("Cannot add more than 50 comments"))

	def on_update(self):
		self.update_comment_in_doc()

	def update_comment_in_doc(self):
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
		# use sql, so that we do not mess with the timestamp
		frappe.db.sql("""update `tab%s` set `_comments`=%s where name=%s""" % (self.comment_doctype,
			"%s", "%s"), (json.dumps(_comments), self.comment_docname))

		comment_doc = frappe.get_doc(self.comment_doctype, self.comment_docname)
		if getattr(comment_doc, "get_route", None):
			clear_cache(comment_doc.get_route())

	def on_trash(self):
		if (self.comment_type or "Comment") != "Comment":
			frappe.only_for("System Manager")

		_comments = self.get_comments_from_parent()
		for c in _comments:
			if c.get("name")==self.name:
				_comments.remove(c)

		self.update_comments_in_parent(_comments)

def on_doctype_update():
	if not frappe.db.sql("""show index from `tabComment`
		where Key_name="comment_doctype_docname_index" """):
		frappe.db.commit()
		frappe.db.sql("""alter table `tabComment`
			add index comment_doctype_docname_index(comment_doctype, comment_docname)""")

