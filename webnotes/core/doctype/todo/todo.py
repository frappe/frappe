# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
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
		