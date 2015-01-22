# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import frappe
import os, sys
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import block_user
from frappe.utils import update_progress_bar

def sync_all(force=0, verbose=False):
	block_user(True)

	for app in frappe.get_installed_apps():
		sync_for(app, force, verbose=verbose)

	block_user(False)

	frappe.clear_cache()

def sync_for(app_name, force=0, sync_everything = False, verbose=False):
	files = []
	for module_name in frappe.local.app_modules.get(app_name) or []:
		folder = os.path.dirname(frappe.get_module(app_name + "." + module_name).__file__)
		files += get_doc_files(folder, force, sync_everything, verbose=verbose)

	l = len(files)
	if l:
		for i, doc_path in enumerate(files):
			import_file_by_path(doc_path, force=force)
			#print module_name + ' | ' + doctype + ' | ' + name

			frappe.db.commit()

			# show progress bar
			update_progress_bar("Updating {0}".format(app_name), i, l)

		print ""


def get_doc_files(start_path, force=0, sync_everything = False, verbose=False):
	"""walk and sync all doctypes and pages"""

	out = []
	document_type = ['doctype', 'page', 'report', 'print_format']
	for doctype in document_type:
		doctype_path = os.path.join(start_path, doctype)
		if os.path.exists(doctype_path):

			# Note: sorted is a hack because custom* and doc* need
			# be synced first

			for docname in sorted(os.listdir(doctype_path)):
				if os.path.isdir(os.path.join(doctype_path, docname)):
					doc_path = os.path.join(doctype_path, docname, docname) + ".json"
					if os.path.exists(doc_path):
						out.append(doc_path)

	return out
