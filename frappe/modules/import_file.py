# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import frappe, os
from frappe.modules import scrub, get_module_path, scrub_dt_dn

def import_files(module, dt=None, dn=None, force=False):
	if type(module) is list:
		out = []
		for m in module:
			out.append(import_file(m[0], m[1], m[2], force=force))
		return out
	else:
		return import_file(module, dt, dn, force=force)
		
def import_file(module, dt, dn, force=False):
	"""Sync a file from txt if modifed, return false if not updated"""
	path = get_file_path(module, dt, dn)
	ret = import_file_by_path(path, force)
	return ret
	
def get_file_path(module, dt, dn):
	dt, dn = scrub_dt_dn(dt, dn)
	
	path = os.path.join(get_module_path(module), 
		os.path.join(dt, dn, dn + '.txt'))
		
	return path
	
def import_file_by_path(path, force=False):
	frappe.flags.in_import = True
	doclist = read_doclist_from_file(path)
	
	if doclist:
		doc = doclist[0]
		
		if not force:
			# check if timestamps match
			if doc['modified']==str(frappe.conn.get_value(doc['doctype'], doc['name'], 'modified')):
				return False
		
		original_modified = doc["modified"]
		
		import_doclist(doclist)

		# since there is a new timestamp on the file, update timestamp in
		frappe.conn.sql("update `tab%s` set modified=%s where name=%s" % \
			(doc['doctype'], '%s', '%s'), 
			(original_modified, doc['name']))
	
	frappe.flags.in_import = False
	return True
	
def read_doclist_from_file(path):
	doclist = None
	if os.path.exists(path):
		from frappe.modules.utils import peval_doclist
		
		with open(path, 'r') as f:
			doclist = peval_doclist(f.read())
	else:
		raise Exception, '%s missing' % path
			
	return doclist

ignore_values = { 
	"Report": ["disabled"], 
}

ignore_doctypes = ["Page Role", "DocPerm"]

def import_doclist(doclist):
	doctype = doclist[0]["doctype"]
	name = doclist[0]["name"]
	old_doc = None
	
	doctypes = set([d["doctype"] for d in doclist])
	ignore = list(doctypes.intersection(set(ignore_doctypes)))
	
	if doctype in ignore_values:
		if frappe.conn.exists(doctype, name):
			old_doc = frappe.doc(doctype, name)

	# delete old
	frappe.delete_doc(doctype, name, force=1, ignore_doctypes=ignore, for_reload=True)
	
	# don't overwrite ignored docs
	doclist1 = remove_ignored_docs_if_they_already_exist(doclist, ignore, name)

	# update old values (if not to be overwritten)
	if doctype in ignore_values and old_doc:
		update_original_values(doclist1, doctype, old_doc)
	
	# reload_new
	new_bean = frappe.bean(doclist1)
	new_bean.ignore_children_type = ignore
	new_bean.ignore_links = True
	new_bean.ignore_validate = True
	new_bean.ignore_permissions = True
	new_bean.ignore_mandatory = True
	new_bean.ignore_restrictions = True
	
	if doctype=="DocType" and name in ["DocField", "DocType"]:
		new_bean.ignore_fields = True
	
	new_bean.insert()

def remove_ignored_docs_if_they_already_exist(doclist, ignore, name):
	doclist1 = doclist
	if ignore:
		has_records = []
		for d in ignore:
			if frappe.conn.get_value(d, {"parent":name}):
				has_records.append(d)
		
		if has_records:
			doclist1 = filter(lambda d: d["doctype"] not in has_records, doclist)
			
	return doclist1

def update_original_values(doclist, doctype, old_doc):
	for key in ignore_values[doctype]:
		doclist[0][key] = old_doc.fields[key]
	