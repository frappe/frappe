# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
	
	def validate(self):
		if self.doc.is_new():
			self.add_comment(webnotes._("Assignment Added"))
		else:
			cur_status = webnotes.conn.get_value("ToDo", self.doc.name, "status")
			if cur_status != self.doc.status:
				self.add_comment(webnotes._("Assignment Status Changed"))
	
	def add_comment(self, text):
		if not self.doc.reference_type and self.doc.reference_name:
			return
			
		comment = webnotes.bean({
			"doctype":"Comment",
			"comment_by": webnotes.session.user,
			"comment_doctype": self.doc.reference_type,
			"comment_docname": self.doc.reference_name,
			"comment": """<div>{text}: 
				<a href='#Form/ToDo/{name}'>{status}: {description}</a></div>""".format(text=text,
					status = webnotes._(self.doc.status),
					name = self.doc.name,
					description = self.doc.description)
		}).insert(ignore_permissions=True)
		
		
# todo is viewable if either owner or assigned_to or System Manager in roles

def get_permission_query_conditions():
	if "System Manager" in webnotes.get_roles():
		return None
	else:
		return """(tabToDo.owner = '{user}' or tabToDo.assigned_by = '{user}')""".format(user=webnotes.session.user)
		
def has_permission(doc):
	if "System Manager" in webnotes.get_roles():
		return True
	else:
		return doc.owner==webnotes.session.user or doc.assigned_by==webnotes.session.user
		