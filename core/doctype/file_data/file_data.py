# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import webnotes, webnotes.utils, os
from webnotes import conf

class DocType():
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def before_insert(self):
		webnotes.local.rollback_observers.append(self)
	
	def on_update(self):
		# check duplicate assignement
		n_records = webnotes.conn.sql("""select count(*) from `tabFile Data`
			where file_name=%s 
			and attached_to_doctype=%s 
			and attached_to_name=%s""", (self.doc.file_name, self.doc.attached_to_doctype,
				self.doc.attached_to_name))[0][0]
		if n_records > 1:
			webnotes.msgprint(webnotes._("Same file has already been attached to the record"))
			raise webnotes.DuplicateEntryError
			
	def on_trash(self):
		if self.doc.attached_to_name:
			# check persmission
			try:
				if not webnotes.has_permission(self.doc.attached_to_doctype, 
					"write", self.doc.attached_to_name):
					webnotes.msgprint(webnotes._("No permission to write / remove."), 
					raise_exception=True)
			except webnotes.DoesNotExistError:
				pass

		# if file not attached to any other record, delete it
		if self.doc.file_name and not webnotes.conn.count("File Data", 
			{"file_name": self.doc.file_name, "name": ["!=", self.doc.name]}):
				if self.doc.file_name.startswith("files/"):
					path = webnotes.utils.get_site_path("public", self.doc.file_name)
				else:
					path = webnotes.utils.get_site_path(conf.files_path, self.doc.file_name)
				if os.path.exists(path):
					os.remove(path)

	def on_rollback(self):
		self.on_trash()