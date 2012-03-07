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
import webnotes

from webnotes.utils import cint, cstr, flt, formatdate, now
from webnotes.model.doc import Document
from webnotes import msgprint, errprint


# -----------------------------------------------------------------------------------------
class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

# *************************** Validate *******************************
	def set_fieldname(self):
		if not self.doc.fieldname:
			# remove special characters from fieldname
			self.doc.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_', cstr(self.doc.label).lower().replace(' ','_'))


	def validate_field(self, doctype_doclist):
		exists = any(d for d in doctype_doclist if d.doctype == 'DocField' and
				(d.fields.get('label') == self.doc.label or 
				d.fields.get('fieldname') == self.doc.fieldname))
		if self.doc.__islocal == 1 and exists:
			msgprint("%s field already exists in Document : %s" % (self.doc.label, self.doc.dt))
			raise Exception

		if self.doc.fieldtype=='Link' and self.doc.options:
			if not webnotes.conn.sql("select name from tabDocType where name=%s", self.doc.options):
				msgprint("%s is not a valid Document" % self.doc.options)
				raise Exception

	def validate(self):
		self.set_fieldname()
		
		from webnotes.model.doctype import get
		temp_doclist = get(self.doc.dt, form=0)
		
		self.validate_field(temp_doclist)
		
		# set idx
		if not self.doc.idx:
			from webnotes.utils import cint
			max_idx = max(d.idx for d in temp_doclist if d.doctype=='DocField')
			self.doc.idx = cint(max_idx) + 1
		
	def on_update(self):
		# update the schema
		from webnotes.model.db_schema import updatedb
		updatedb(self.doc.dt)

		from webnotes.utils.cache import CacheItem
		CacheItem(self.doc.dt).clear()

	def on_trash(self):
		pass
		# delete property setter entries
