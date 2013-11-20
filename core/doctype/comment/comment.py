# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		if webnotes.conn.sql("""select count(*) from tabComment where comment_doctype=%s
			and comment_docname=%s""", (self.doc.doctype, self.doc.name))[0][0] >= 50:
			webnotes.msgprint("Max Comments reached!", raise_exception=True)
			
	def on_update(self):
		try:
			import startup.event_handlers
			if hasattr(startup.event_handlers, 'comment_added'):
				startup.event_handlers.comment_added(self.doc)
		except ImportError, e:
			pass

def on_doctype_update():
	if not webnotes.conn.sql("""show index from `tabComment` 
		where Key_name="comment_doctype_docname_index" """):
		webnotes.conn.commit()
		webnotes.conn.sql("""alter table `tabComment` 
			add index comment_doctype_docname_index(comment_doctype, comment_docname)""")