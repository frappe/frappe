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
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import webnotes, webnotes.utils, os

class DocType():
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		# check duplicate assignement
		if webnotes.conn.sql("""select count(*) from `tabFile Data`
			where file_name=%s 
			and attached_to_doctype=%s 
			and attached_to_name=%s""", (doc.file_name, doc.attached_to_doctype,
				doc.attached_to_name))[0][0] > 1:
			webnotes.msgprint(webnotes._("Same file has already been attached to the record"))
			raise webnotes.DuplicateEntryError
			
	def on_trash(self):
		path = webnotes.utils.get_path("public", "files", self.doc.file_name)
		if os.path.exists(path):
			os.remove(path)
		