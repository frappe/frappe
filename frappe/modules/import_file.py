# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import frappe, os, json
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
	doc = read_doc_from_file(path)
	
	if doc:
		if not force:
			# check if timestamps match
			if doc['modified']==str(frappe.db.get_value(doc['doctype'], doc['name'], 'modified')):
				return False
		
		original_modified = doc["modified"]
		
		import_doc(doc)

		# since there is a new timestamp on the file, update timestamp in
		frappe.db.sql("update `tab%s` set modified=%s where name=%s" % \
			(doc['doctype'], '%s', '%s'), 
			(original_modified, doc['name']))
	
	frappe.flags.in_import = False
	return True
	
def read_doc_from_file(path):
	doc = None
	if os.path.exists(path):
		with open(path, 'r') as f:
			doc = json.loads(f.read())
	else:
		raise Exception, '%s missing' % path
			
	return doc

ignore_values = { 
	"Report": ["disabled"], 
}

ignore_doctypes = ["Page Role", "DocPerm"]

def import_doc(docdict):
	docdict["__islocal"] = 1
	doc = frappe.get_doc(docdict)

	old_doc = None
	if doctype in ignore_values:
		if frappe.db.exists(doc.doctype, doc.name):
			old_doc = frappe.get_doc(doc.doctype, doc.name)
		
		# update ignore values
		for key in ignore_values.get(doctype) or []:
			doc.set(key, old_doc.get(key))
			
	# update ignored docs into new doc
	for df in doc.get_table_fields():
		if df.options in ignore_doctypes:
			doc.set(df.fieldname, [])
	
	# delete old
	frappe.delete_doc(doctype, name, force=1, ignore_doctypes=ignore, for_reload=True)
	
	doc.ignore_children_type = ignore
	doc.ignore_links = True
	doc.ignore_validate = True
	doc.ignore_permissions = True
	doc.ignore_mandatory = True
	doc.ignore_restrictions = True
	doc.insert()
	