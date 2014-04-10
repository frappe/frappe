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
	return import_files(module, dt, dn, force=force)

def export_doc(doctype, name, module=None):
	"""write out a doc"""
	from frappe.modules.export_file import write_document_file

	if not module: module = frappe.db.get_value(doctype, name, 'module')
	write_document_file(frappe.get_doc(doctype, name), module)

def get_doctype_module(doctype):
	return frappe.db.get_value('DocType', doctype, 'module') or "core"

def load_doctype_module(doctype, module=None, prefix=""):
	if not module:
		module = get_doctype_module(doctype)
	return frappe.get_module(get_module_name(doctype, module, prefix))
	
def get_module_name(doctype, module, prefix=""):
	from frappe.modules import scrub
	return '{app}.{module}.doctype.{doctype}.{prefix}{doctype}'.format(\
		app = scrub(frappe.local.module_app[scrub(module)]), 
		module = scrub(module), doctype = scrub(doctype), prefix=prefix)
