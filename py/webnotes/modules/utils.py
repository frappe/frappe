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
def listfolders(path, only_name=0):
	"""
		Returns the list of folders (with paths) in the given path, 
		If only_name is set, it returns only the folder names
	"""

	import os
	out = []
	for each in os.listdir(path):
		dirname = each.split(os.path.sep)[-1]
		fullpath = os.path.join(path, dirname)

		if os.path.isdir(fullpath) and not dirname.startswith('.'):
			out.append(only_name and dirname or fullname)
	return out

def switch_module(dt, dn, to, frm=None, export=None):
	"""
		Change the module of the given doctype, if export is true, then also export txt and copy
		code files from src
	"""
	import os
	webnotes.conn.sql("update `tab"+dt+"` set module=%s where name=%s", (to, dn))

	if export:
		export_doc(dt, dn)

		# copy code files
		if dt in ('DocType', 'Page', 'Search Criteria', 'Report'):
			from_path = os.path.join(get_module_path(frm), scrub(dt), scrub(dn), scrub(dn))
			to_path = os.path.join(get_module_path(to), scrub(dt), scrub(dn), scrub(dn))

			# make dire if exists
			os.system('mkdir -p %s' % os.path.join(get_module_path(to), scrub(dt), scrub(dn)))

			for ext in ('py','js','html','css'):
				os.system('cp %s %s')
