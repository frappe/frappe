# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
	Utilities for using modules
"""
import frappe, os
import frappe.utils

lower_case_files_for = ['DocType', 'Page', 'Report', 
	"Workflow", 'Module Def', 'Desktop Item', 'Workflow State', 'Workflow Action']

def scrub(txt):
	return frappe.scrub(txt)
	
def scrub_dt_dn(dt, dn):
	"""Returns in lowercase and code friendly names of doctype and name for certain types"""
	ndt, ndn = dt, dn
	if dt in lower_case_files_for:
		ndt, ndn = scrub(dt), scrub(dn)

	return ndt, ndn
			
def get_module_path(module):
	"""Returns path of the given module"""
	return frappe.get_module_path(module)
	
def get_doc_path(module, doctype, name):
	dt, dn = scrub_dt_dn(doctype, name)
	return os.path.join(get_module_path(module), dt, dn)

def reload_doc(module, dt=None, dn=None, force=True):
	from frappe.modules.import_file import import_files
	return import_files(scrub(module), scrub(dt), scrub(dn), force=force)

def export_doc(doctype, name, module=None):
	"""write out a doc"""
	from frappe.modules.export_file import write_document_file
	import frappe.model.doc

	if not module: module = frappe.db.get_value(doctype, name, 'module')
	write_document_file(frappe.model.doc.get(doctype, name), module)

def get_doctype_module(doctype):
	return frappe.db.get_value('DocType', doctype, 'module') or "core"
