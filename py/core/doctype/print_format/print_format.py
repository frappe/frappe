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

import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl
	
	def on_update(self):
		"""
			On update, create/update a DocFormat record corresponding to DocType and Print Format Name
		"""
		if self.doc.doc_type:
			from webnotes.model.doc import Document
			res = webnotes.conn.sql("""
				SELECT * FROM `tabDocFormat`
				WHERE format=%s and docstatus<2""", self.doc.name)
			if res and res[0]:
				d = Document('DocFormat', res[0][0])
				d.parent = self.doc.doc_type
				d.parenttype = 'DocType'
				d.parentfield = 'formats'
				d.format = self.doc.name
				d.save()
			else:
				max_idx = webnotes.conn.sql("""
					SELECT MAX(idx) FROM `tabDocFormat`
					WHERE parent=%s
					AND parenttype='DocType'
					AND parentfield='formats'""", self.doc.doc_type)[0][0]
				if not max_idx: max_idx = 0
				d = Document('DocFormat')
				d.parent = self.doc.doc_type
				d.parenttype = 'DocType'
				d.parentfield = 'formats'
				d.format = self.doc.name
				d.idx = max_idx + 1
				d.save(1)
