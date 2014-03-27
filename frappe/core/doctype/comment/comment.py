# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.website.render import clear_cache

from frappe.model.document import Document

class Comment(Document):
		
	def validate(self):
		if frappe.db.sql("""select count(*) from tabComment where comment_doctype=%s
			and comment_docname=%s""", (self.doc.doctype, self.doc.name))[0][0] >= 50:
			frappe.msgprint("Max Comments reached!", raise_exception=True)
	
	def on_update(self):
		self.update_comment_in_doc()
		
	def update_comment_in_doc(self):
		if self.doc.comment_doctype and self.doc.comment_docname and self.doc.comment:
			try:
				_comments = self.get_comments_from_parent()
				updated = False
				for c in _comments:
					if c.get("name")==self.doc.name:
						c["comment"] = self.doc.comment
						updated = True
						
				if not updated:
					_comments.append({
						"comment": self.doc.comment, 
						"by": self.doc.comment_by or self.doc.owner, 
						"name":self.doc.name
					})
				self.update_comments_in_parent(_comments)
			except Exception, e:
				if e.args[0]==1054:
					from frappe.model.db_schema import add_column
					add_column(self.doc.comment_doctype, "_comments", "Text")
					self.update_comment_in_doc()
				elif e.args[0]==1146:
					# no table
					pass
				else:
					raise
	
	def get_comments_from_parent(self):
		_comments = frappe.db.get_value(self.doc.comment_doctype, 
			self.doc.comment_docname, "_comments") or "[]"
		return json.loads(_comments)
	
	def update_comments_in_parent(self, _comments):
		# use sql, so that we do not mess with the timestamp
		frappe.db.sql("""update `tab%s` set `_comments`=%s where name=%s""" % (self.doc.comment_doctype,
			"%s", "%s"), (json.dumps(_comments), self.doc.comment_docname))
			
		# clear parent cache if route exists:
		route = frappe.db.get_value("Website Route", {"ref_doctype": self.doc.comment_doctype, 
			"docname": self.doc.comment_docname})
			
		if route:
			clear_cache(route)
	
	def on_trash(self):
		_comments = self.get_comments_from_parent()
		for c in _comments:
			if c.get("name")==self.doc.name:
				_comments.remove(c)
		
		self.update_comments_in_parent(_comments)
		
def on_doctype_update():
	if not frappe.db.sql("""show index from `tabComment` 
		where Key_name="comment_doctype_docname_index" """):
		frappe.db.commit()
		frappe.db.sql("""alter table `tabComment` 
			add index comment_doctype_docname_index(comment_doctype, comment_docname)""")