# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 
from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.doc.name = self.doc.dt + "-" + self.doc.script_type

	def on_update(self):
		if self.doc.script_type == 'Client':
			webnotes.clear_cache(doctype=self.doc.dt)
		else:
			webnotes.cache().delete_value("_server_script:" + self.doc.dt)
	
	def on_trash(self):
		if self.doc.script_type == 'Client':
			webnotes.clear_cache(doctype=self.doc.dt)
		else:
			webnotes.cache().delete_value("_server_script:" + self.doc.dt)

def get_custom_server_script(doctype):
	custom_script = webnotes.cache().get_value("_server_script:" + doctype)
	if custom_script==None:
		custom_script = webnotes.conn.get_value("Custom Script", {"dt": doctype, "script_type":"Server"}, 
			"script") or ""
		webnotes.cache().set_value("_server_script:" + doctype, custom_script)
		
	return custom_script

