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

# Please edit this list and import only required elements
from __future__ import unicode_literals
import webnotes
from webnotes.utils import cint

	
# -----------------------------------------------------------------------------------------

class DocType:
	def __init__(self,d,dl):
		self.doc, self.doclist = d,dl

	def autoname(self):
		self.doc.name = self.doc.criteria_name.lower().replace('(','').replace(')', '')\
			.replace('.','').replace(',','').replace('"', '').replace("'",'').replace(' ', '_')\
			.replace('/', '-')
		
		# for duplicates
		if webnotes.conn.sql("select name from `tabSearch Criteria` where name = %s", self.doc.name):
			m = webnotes.conn.sql("select name from `tabSearch Criteria` where name like '%s%%' order by name desc limit 1" % self.doc.name)[0][0]
			self.doc.name = self.doc.name + str(cint(m[-1]) + 1)

	def set_module(self):
		if not self.doc.module:
			doctype_module = webnotes.conn.sql("select module from tabDocType where name = '%s'" % (self.doc.doc_type))
			webnotes.conn.set(self.doc,'module',doctype_module and doctype_module[0][0] or 'NULL')

	def validate(self):
		if webnotes.conn.sql("select name from `tabSearch Criteria` where \
				criteria_name=%s and name!=%s", (self.doc.criteria_name,
					self.doc.name)):
			webnotes.msgprint("Criteria Name '%s' already used, please use another name" % self.doc.criteria_name, raise_exception = 1)

	def on_update(self):
		self.set_module()
		self.export_doc()
	
	def export_doc(self):
		# export
		import conf
		if self.doc.standard == 'Yes' and getattr(conf, 'developer_mode', 0) == 1:
			from webnotes.modules.export_module import export_to_files
			export_to_files(record_list=[['Search Criteria', self.doc.name]])

	# patch to rename search criteria from old style numerical to
	# new style based on criteria name
	def rename(self):
		old_name = self.doc.name
		
		if not self.doc.module:
			self.set_module()
		
		self.autoname()
		webnotes.conn.sql("update `tabSearch Criteria` set name=%s where name=%s", (self.doc.name, old_name))
		
	def rename_export(self, old_name):
				
		# export the folders
		self.export_doc()
		import os, shutil
		from webnotes.modules import get_module_path, scrub
		
		path = os.path.join(get_module_path(self.doc.module), 'search_criteria', scrub(old_name))
		
		# copy py/js files
		self.copy_file(path, scrub(old_name), '.py')
		self.copy_file(path, scrub(old_name), '.js')
		self.copy_file(path, scrub(old_name), '.sql')

	def copy_file(self, path, old_name, extn):
		import os
		from webnotes.modules import get_module_path, scrub

		if os.path.exists(os.path.join(path, old_name + extn)):
			os.system('cp %s %s' % (os.path.join(path, old_name + extn), \
			os.path.join(get_module_path(self.doc.module), 'search_criteria', scrub(self.doc.name), scrub(self.doc.name) + extn)))
	
