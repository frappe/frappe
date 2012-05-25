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

from webnotes import msgprint

sql = webnotes.conn.sql
	
# -----------------------------------------------------------------------------------------

	
class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist
	
	# Autoname is Email id
	# --------------------

	def autoname(self):
		import re
		from webnotes.utils import validate_email_add

		if self.doc.name not in ('Guest','Administrator'):
			self.doc.email = self.doc.email.strip()
			if not validate_email_add(self.doc.email):
				msgprint("%s is not a valid email id" % self.doc.email)
				raise Exception
		
			self.doc.name = self.doc.email
	
	def on_update(self):
		# owner is always name
		if not self.doc.password:
			webnotes.conn.set(self.doc, 'password' ,'password')
		webnotes.conn.set(self.doc, 'owner' ,self.doc.name)

	def get_fullname(self):
		return (self.doc.first_name or '') + \
			(self.doc.first_name and " " or '') + (self.doc.last_name or '')
			
	def on_rename(self,newdn,olddn):
		tables = webnotes.conn.sql("show tables")
		for tab in tables:
			desc = webnotes.conn.sql("desc `%s`" % tab[0], as_dict=1)
			has_fields = []
			for d in desc:
				if d.get('Field') in ['owner', 'modified_by']:
					has_fields.append(d.get('Field'))
			for field in has_fields:
				webnotes.conn.sql("""\
					update `%s` set `%s`=%s
					where `%s`=%s""" % \
					(tab[0], field, '%s', field, '%s'), (newdn, olddn))