# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
	Execute Patch Files

	To run directly
	
	python lib/wnf.py patch patch1, patch2 etc
	python lib/wnf.py patch -f patch1, patch2 etc
	
	where patch1, patch2 is module name
"""
import webnotes, os

class PatchError(Exception): pass

def run_all():
	"""run all pending patches"""
	executed = [p[0] for p in webnotes.conn.sql("""select patch from `tabPatch Log`""")]
		
	for patch in get_all_patches():
		if patch and (patch not in executed):
			if not run_single(patchmodule = patch):
				log(patch + ': failed: STOPPED')
				raise PatchError(patch)
				
def get_all_patches():
	patches = []
	for app in webnotes.get_installed_apps():
		patches.extend(webnotes.get_file_items(webnotes.get_pymodule_path(app, "patches.txt")))
			
	return patches

def reload_doc(args):
	import webnotes.modules
	run_single(method = webnotes.modules.reload_doc, methodargs = args)

def run_single(patchmodule=None, method=None, methodargs=None, force=False):
	from webnotes import conf
	
	# don't write txt files
	conf.developer_mode = 0
	
	if force or method or not executed(patchmodule):
		return execute_patch(patchmodule, method, methodargs)
	else:
		return True
		
def execute_patch(patchmodule, method=None, methodargs=None):
	"""execute the patch"""
	success = False
	block_user(True)
	webnotes.conn.begin()
	try:
		log('Executing %s in %s' % (patchmodule or str(methodargs), webnotes.conn.cur_db_name))
		if patchmodule:
			if patchmodule.startswith("execute:"):
				exec patchmodule.split("execute:")[1] in globals()
			else:
				webnotes.get_attr(patchmodule + ".execute")()
			update_patch_log(patchmodule)
		elif method:
			method(**methodargs)
			
		webnotes.conn.commit()
		success = True
	except Exception, e:
		webnotes.conn.rollback()
		tb = webnotes.get_traceback()
		log(tb)
		import os
		if webnotes.request:
			add_to_patch_log(tb)

	block_user(False)
	if success:
		log('Success')
	return success

def add_to_patch_log(tb):
	"""add error log to patches/patch.log"""
	import conf, os
	# TODO use get_site_base_path
	with open(os.path.join(os.path.dirname(conf.__file__), 'app', 'patches','patch.log'),'a') as patchlog:
		patchlog.write('\n\n' + tb)
	
def update_patch_log(patchmodule):
	"""update patch_file in patch log"""	
	if webnotes.conn.table_exists("__PatchLog"):
		webnotes.conn.sql("""INSERT INTO `__PatchLog` VALUES (%s, now())""", \
			patchmodule)
	else:
		webnotes.doc({"doctype": "Patch Log", "patch": patchmodule}).insert()

def executed(patchmodule):
	"""return True if is executed"""
	if webnotes.conn.table_exists("__PatchLog"):
		done = webnotes.conn.sql("""select patch from __PatchLog where patch=%s""", patchmodule)
	else:
		done = webnotes.conn.get_value("Patch Log", {"patch": patchmodule})
	if done:
		print "Patch %s executed in %s" % (patchmodule, webnotes.conn.cur_db_name)
	return done
	
def block_user(block):
	"""stop/start execution till patch is run"""
	webnotes.conn.begin()
	msg = "Patches are being executed in the system. Please try again in a few moments."
	webnotes.conn.set_global('__session_status', block and 'stop' or None)
	webnotes.conn.set_global('__session_status_message', block and msg or None)
	webnotes.conn.commit()

def setup():
	webnotes.conn.sql("""CREATE TABLE IF NOT EXISTS `__PatchLog` (
			patch TEXT, applied_on DATETIME) engine=InnoDB""")
		
def log(msg):
	if getattr(webnotes.local, "patch_log_list", None) is None:
		webnotes.local.patch_log_list = []
	
	webnotes.local.patch_log_list.append(msg)
