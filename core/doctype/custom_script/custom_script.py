# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 
from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.doc.name = self.doc.dt + "-" + self.doc.script_type

	def validate(self):
		if self.doc.script_type=="Server" and webnotes.session.user!="Administrator":
			webnotes.throw("Only Administrator is allowed to edit Server Script")

		if not self.doc.script.startswith("\n"):
			self.doc.script = "\n" + self.doc.script

	def on_update(self):
		webnotes.clear_cache(doctype=self.doc.dt)
		webnotes.cache().delete_value("_server_script:" + self.doc.dt)
	
	def on_trash(self):
		webnotes.clear_cache(doctype=self.doc.dt)
		webnotes.cache().delete_value("_server_script:" + self.doc.dt)

def get_custom_server_script(doctype):
	from webnotes.modules import scrub
	from webnotes import conf
	from webnotes.utils import get_site_path
	import os
	custom_script = webnotes.cache().get_value("_server_script:" + doctype)
	if not custom_script:
		script_path = get_site_path(conf.custom_scripts_path, scrub(doctype) + '.py')
		if os.path.exists(script_path):
			with open(script_path, 'r') as f:
				custom_script = f.read()
		else:
			custom_script = None
		webnotes.cache().set_value("_server_script:" + doctype, custom_script)
	
	return custom_script

