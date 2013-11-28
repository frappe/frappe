# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.doc.name = self.doc.dt + "-" + self.doc.script_type

	def on_update(self):
		webnotes.clear_cache(doctype=self.doc.dt)
	
	def on_trash(self):
		webnotes.clear_cache(doctype=self.doc.dt)

def make_custom_server_script_file(doctype, script=None):
	import os
	from webnotes.plugins import get_path

	file_path = get_path(None, "DocType", doctype)
	if os.path.exists(file_path):
		raise IOError(file_path + " already exists")
		
	# create folder if not exists
	webnotes.create_folder(os.path.dirname(file_path))
	
	# create file
	custom_script = """from __future__ import unicode_literals
import webnotes
from webnotes.utils import cint, cstr, flt
from webnotes.model.doc import Document
from webnotes.model.code import get_obj
from webnotes import msgprint, _

class CustomDocType(DocType):
{script}""".format(script=script or "\tpass")

	with open(file_path, "w") as f:
		f.write(custom_script.encode("utf-8"))