# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

def get_code_and_execute(module, doctype, docname, plugin=None, namespace=None):
	code = get_code(module, doctype, docname, plugin)
	return exec_code(code, namespace)

def exec_code(code, namespace=None):
	if namespace is None: namespace = {}

	if code:
		exec code in namespace
	
	return namespace
	
def get_code(module, doctype, docname, plugin=None):	
	try:
		code = read_file(module, doctype, docname, plugin, cache=True)
	except webnotes.SQLError:
		return None
		
	return code
	
def get_cache_key(doctype, docname, extn="py"):
	from webnotes.modules import scrub
	return "plugin_file:{doctype}:{docname}:{extn}".format(doctype=scrub(doctype), 
		docname=scrub(docname), extn=scrub(extn))
	
def get_plugin_name(doctype=None, docname=None):
	import os
	from webnotes.utils import get_site_base_path
	plugin = None
	
	if doctype:
		meta = webnotes.get_doctype(doctype)
		if meta.get_field("plugin"):
			plugin = webnotes.conn.get_value(doctype, docname, "plugin")
	
	if not plugin:
		plugin = os.path.basename(get_site_base_path())

	return plugin
	
def read_file(module, doctype, docname, plugin=None, extn="py", cache=False):
	import os
	content = None
	
	if cache:
		content = webnotes.cache().get_value(get_cache_key(doctype, docname, extn))
		
	if not content:
		path = get_path(module, doctype, docname, plugin, extn)
		if os.path.exists(path):
			with open(path, 'r') as f:
				content = f.read() or "Does Not Exist"
	
	if cache:
		webnotes.cache().set_value(get_cache_key(doctype, docname, extn), content)
		
	return None if (content == "Does Not Exist") else content
	
def get_path(module, doctype, docname, plugin=None, extn="py"):
	from webnotes.modules import scrub
	import os
	
	if not module: module = webnotes.conn.get_value(doctype, docname, "module")
	if not plugin: plugin = get_plugin_name(doctype, docname)
	
	# site_abs_path/plugins/module/doctype/docname/docname.py
	return os.path.join(get_plugin_path(scrub(plugin)), scrub(module),
		scrub(doctype), scrub(docname), scrub(docname) + "." + extn)

def get_plugin_path(plugin=None):
	from webnotes.modules import scrub
	from webnotes.utils import get_site_path
	if not plugin: plugin = get_plugin_name(None, None)
	
	return get_site_path(webnotes.conf.get("plugins_path"), scrub(plugin))
	
def remove_init_files():
	import os
	from webnotes.utils import get_site_path, cstr
	for path, folders, files in os.walk(get_site_path(webnotes.conf.get("plugins_path"))):
		for f in files:
			# cstr(f) is required when filenames are non-ascii
			if cstr(f) in ("__init__.py", "__init__.pyc"):
				os.remove(os.path.join(path, f))
				
def clear_cache(doctype=None, docname=None):
	import os
	from webnotes.utils import get_site_path
	
	def clear_single(dt, dn):
		webnotes.cache().delete_value(get_cache_key(dt, dn, "py"))
		webnotes.cache().delete_value(get_cache_key(dt, dn, "js"))
		
	if not (doctype and docname):
		for path, folders, files in os.walk(get_site_path(webnotes.conf.get("plugins_path"))):
			if files:
				dt = os.path.basename(os.path.dirname(path))
				dn = os.path.basename(path)
				clear_single(dt, dn)
	else:
		clear_single(doctype, docname)
		