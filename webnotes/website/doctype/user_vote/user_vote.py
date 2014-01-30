# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
	
	def validate(self):
		# if new
		if self.doc.fields.get("__islocal"):
			if webnotes.conn.get_value("User Vote", {"ref_doctype": self.doc.ref_doctype, 
				"ref_name": self.doc.ref_name, "owner": webnotes.session.user}):
				
				raise webnotes.DuplicateEntryError
			
	def on_update(self):
		self.update_ref_count()

	def on_trash(self):
		self.update_ref_count(-1)

	def update_ref_count(self, cnt=0):
		count = webnotes.conn.sql("""select count(*) from `tabUser Vote` where ref_doctype=%s and ref_name=%s""",
			(self.doc.ref_doctype, self.doc.ref_name))[0][0]
		webnotes.conn.set_value(self.doc.ref_doctype, self.doc.ref_name, "upvotes", count + cnt)
		
def on_doctype_update():
	webnotes.conn.add_index("User Vote", ["ref_doctype", "ref_name"])
