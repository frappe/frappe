# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import cint

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		if cint(self.doc.fields.get("__islocal")) and webnotes.conn.exists("UserRole", {
				"parent": self.doc.parent, "role": self.doc.role}):
			webnotes.msgprint("Role Already Exists", raise_exception=True)
			