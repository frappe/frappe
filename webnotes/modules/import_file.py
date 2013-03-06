# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals

import webnotes, os
from webnotes.modules import scrub, get_module_path, scrub_dt_dn

in_import = False

def import_files(module, dt=None, dn=None, force=False):
	if type(module) is list:
		for m in module:
			return import_file(m[0], m[1], m[2], force)
	else:
		return import_file(module, dt, dn, force)
		
def import_file(module, dt, dn, force=False):
	"""Sync a file from txt if modifed, return false if not updated"""
	global in_import
	in_import = True
	dt, dn = scrub_dt_dn(dt, dn)
	path = os.path.join(get_module_path(module), 
		os.path.join(dt, dn, dn + '.txt'))
		
	ret = import_file_by_path(path, force)
	in_import = False
	return ret

def import_file_by_path(path, force=False):
	if os.path.exists(path):
		from webnotes.modules.utils import peval_doclist
		
		with open(path, 'r') as f:
			doclist = peval_doclist(f.read())
					
		if doclist:
			doc = doclist[0]
			if not force:
				# check if timestamps match
				if doc['modified']== str(webnotes.conn.get_value(doc['doctype'], doc['name'], 'modified')):
					return False
			
			import_doclist(doclist)

			# since there is a new timestamp on the file, update timestamp in
			webnotes.conn.sql("update `tab%s` set modified=%s where name=%s" % \
				(doc['doctype'], '%s', '%s'), 
				(doc['modified'],doc['name']))
			return True
	else:
		raise Exception, '%s missing' % path

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
		if webnotes.conn.exists(doctype, name):
			old_doc = webnotes.doc(doctype, name)

	# delete old
	webnotes.delete_doc(doctype, name, force=1, ignore_doctypes =ignore, for_reload=True)
	
	# don't overwrite ignored docs
	doclist1 = remove_ignored_docs_if_they_already_exist(doclist, ignore, name)

	# update old values (if not to be overwritten)
	if doctype in ignore_values and old_doc:
		update_original_values(doclist1, doctype, old_doc)
	
	# reload_new
	new_bean = webnotes.bean(doclist1)
	new_bean.ignore_children_type = ignore
	new_bean.ignore_check_links = True
	new_bean.ignore_validate = True
	
	if doctype=="DocType" and name in ["DocField", "DocType"]:
		new_bean.ignore_fields = True
	
	new_bean.insert()

def remove_ignored_docs_if_they_already_exist(doclist, ignore, name):
	doclist1 = doclist
	if ignore:
		has_records = []
		for d in ignore:
			if webnotes.conn.get_value(d, {"parent":name}):
				has_records.append(d)
		
		if has_records:
			doclist1 = filter(lambda d: d["doctype"] not in has_records, doclist)
			
	return doclist1

def update_original_values(doclist, doctype, old_doc):
	for key in ignore_values[doctype]:
		doclist[0][key] = old_doc.fields[key]
	