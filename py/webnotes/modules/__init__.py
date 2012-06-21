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

"""
	Utilities for using modules
"""
import webnotes

transfer_types = ['Role', 'Print Format','DocType','Page','DocType Mapper','GL Mapper','Search Criteria', 'Patch']

def scrub(txt):
	return txt.replace(' ','_').replace('-', '_').replace('/', '_').lower()

def scrub_dt_dn(dt, dn):
	"""Returns in lowercase and code friendly names of doctype and name for certain types"""
	ndt, ndn = dt, dn
	if dt.lower() in ('doctype', 'search criteria', 'page'):
		ndt, ndn = scrub(dt), scrub(dn)

	return ndt, ndn
			
def get_module_path(module):
	"""Returns path of the given module"""
	import os, conf
	m = scrub(module)
	
	if m in ('core'):
		path_to_lib = os.sep.join(conf.modules_path.split(os.path.sep)[:-1])
		return os.path.join(path_to_lib, 'lib', 'py', 'core')
	else:
		return os.path.join(conf.modules_path, m)
	

def reload_doc(module, dt=None, dn=None):
	"""reload single / list of records"""

	if type(module) is list:
		for m in module:
			reload_single_doc(m[0], m[1], m[2])
	else:
		reload_single_doc(module, dt, dn)
		
def reload_single_doc(module, dt, dn, force=False):
	"""Sync a file from txt if modifed, return false if not updated"""
	if dt.lower() == 'doctype':
		return
		
	import os
	dt, dn = scrub_dt_dn(dt, dn)

	path = os.path.join(get_module_path(module), 
		os.path.join(dt, dn, dn + '.txt'))
		
	if os.path.exists(path):
		from webnotes.model.utils import peval_doclist
		
		with open(path, 'r') as f:
			doclist = peval_doclist(f.read())
			
		if doclist:
			doc = doclist[0]
			if not force:
				# check if timestamps match
				if doc['modified']== str(webnotes.conn.get_value(doc['doctype'], doc['name'], 'modified')):
					return False
			
			from webnotes.utils.transfer import set_doc
			set_doc(doclist, 1, 1, 1)

			# since there is a new timestamp on the file, update timestamp in
			webnotes.conn.sql("update `tab%s` set modified=%s where name=%s" % \
				(doc['doctype'], '%s', '%s'), 
				(doc['modified'],doc['name']))
			return True
	else:
		raise Exception, '%s missing' % path


def export_doc(doctype, name, module=None):
	"""write out a doc"""
	from webnotes.modules.export_module import write_document_file
	import webnotes.model.doc
	if not module: module = webnotes.conn.get_value(doctype, name, 'module')
	doclist = [d.fields for d in webnotes.model.doc.get(doctype, name)]
	write_document_file(doclist, module)

def get_all_modules():
	"""Return list of all modules"""
	import conf
	from webnotes.modules.utils import listfolders

	if hasattr(conf, 'modules_path'):
		return listfolders(conf.modules_path, 1)
			
		
