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

def import_files(module, dt=None, dn=None):
	if type(module) is list:
		for m in module:
			import_file(m[0], m[1], m[2])
	else:
		import_file(module, dt, dn)
		
def import_file(module, dt, dn, force=False):
	"""Sync a file from txt if modifed, return false if not updated"""
	if dt.lower() == 'doctype':
		return
		
	dt, dn = scrub_dt_dn(dt, dn)

	path = os.path.join(get_module_path(module), 
		os.path.join(dt, dn, dn + '.txt'))
		
	import_file_by_path(path, force)

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
			
			from webnotes.modules.import_merge import set_doc
			set_doc(doclist, 1, 1, 1)

			# since there is a new timestamp on the file, update timestamp in
			webnotes.conn.sql("update `tab%s` set modified=%s where name=%s" % \
				(doc['doctype'], '%s', '%s'), 
				(doc['modified'],doc['name']))
			return True
	else:
		raise Exception, '%s missing' % path

