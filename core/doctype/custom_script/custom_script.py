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
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.doc.name = self.doc.dt + "-" + self.doc.script_type

	def on_update(self):
		if self.doc.script_type == 'Client':
			webnotes.clear_cache(doctype=self.doc.dt)
		else:
			webnotes.cache().delete_value("_server_script:" + self.doc.dt)
	
	def on_trash(self):
		if self.doc.script_type == 'Client':
			webnotes.clear_cache(doctype=self.doc.dt)
		else:
			webnotes.cache().delete_value("_server_script:" + self.doc.dt)

def get_custom_server_script(doctype):
	custom_script = webnotes.cache().get_value("_server_script:" + doctype)
	if custom_script==None:
		custom_script = webnotes.conn.get_value("Custom Script", {"dt": doctype, "script_type":"Server"}, 
			"script") or ""
		webnotes.cache().set_value("_server_script:" + doctype, custom_script)
		
	return custom_script

