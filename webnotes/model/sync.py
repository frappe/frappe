# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import webnotes
import os, sys
from webnotes.modules.import_file import import_file_by_path
from webnotes.utils import get_path, cstr

def sync_all(force=0):
	for app in webnotes.get_installed_apps():
		sync_for(app, force)
	webnotes.clear_cache()

def sync_for(app_name, force=0, sync_everything = False, verbose=False):
	for module_name in webnotes.local.app_modules[app_name]:
		folder = os.path.dirname(webnotes.get_module(app_name + "." + module_name).__file__)
		walk_and_sync(folder, force, sync_everything, verbose=verbose)

def walk_and_sync(start_path, force=0, sync_everything = False, verbose=False):
	"""walk and sync all doctypes and pages"""

	modules = []
	
	document_type = ['doctype', 'page', 'report']

	for path, folders, files in os.walk(start_path):
		# sort folders so that doctypes are synced before pages or reports

		for dontwalk in (".git", "locale", "public"):
			if dontwalk in folders: 
				folders.remove(dontwalk)

		folders.sort()

		if sync_everything or (os.path.basename(os.path.dirname(path)) in document_type):
			for f in files:
				f = cstr(f)
				if f.endswith(".txt"):
					doc_name = f.split(".txt")[0]
					if doc_name == os.path.basename(path):

						module_name = path.split(os.sep)[-3]
						doctype = path.split(os.sep)[-2]
						name = path.split(os.sep)[-1]
						
						if import_file_by_path(os.path.join(path, f), force=force) and verbose:
							print module_name + ' | ' + doctype + ' | ' + name

						webnotes.conn.commit()
					
	return modules
