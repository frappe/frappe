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

	def on_update(self):
		webnotes.clear_cache(doctype=self.doc.dt)
	
	def on_trash(self):
		webnotes.clear_cache(doctype=self.doc.dt)

def get_custom_server_script(doctype, plugin=None):
	import os, MySQLdb
	custom_script = webnotes.cache().get_value("_server_script:" + doctype)

	if not custom_script:
		try:
			script_path = get_custom_server_script_path(doctype, plugin)
			if os.path.exists(script_path):
				with open(script_path, 'r') as f:
					custom_script = f.read()
			else:
				custom_script = "Does Not Exist"
			webnotes.cache().set_value("_server_script:" + doctype, custom_script)
		except (webnotes.DoesNotExistError, MySQLdb.OperationalError):
			# this happens when syncing
			return None

	return None if custom_script == "Does Not Exist" else custom_script
	
def make_custom_server_script_file(doctype, script=None):
	import os

	file_path = get_custom_server_script_path(doctype)
	if os.path.exists(file_path):
		raise Exception(file_path + " already exists")
		
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
		f.write(custom_script)
		
def get_custom_server_script_path(doctype, plugin=None):
	from webnotes.modules import scrub, get_plugin_path
	from webnotes.utils import get_site_base_path
	import os
	
	# check if doctype exists
	opts = webnotes.conn.get_value("DocType", doctype, ["name", "module", "plugin"])
	if not opts:
		raise webnotes.DoesNotExistError("""DocType "{doctype}" does not exist""".format(doctype=doctype))
	
	name, module, doctype_plugin = opts
	if not plugin:
		plugin = doctype_plugin or os.path.basename(get_site_base_path())
	
	# site_abs_path/plugin_name/module_name/doctype/doctype_name/doctype_name.py
	path = os.path.join(get_plugin_path(scrub(plugin)), scrub(module),
		"doctype", scrub(doctype), scrub(doctype) + ".py")
		
	return path
