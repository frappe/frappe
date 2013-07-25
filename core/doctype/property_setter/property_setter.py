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
		self.doc.name = self.doc.doc_type + "-" \
			+ (self.doc.field_name and (self.doc.field_name + "-")  or "") \
			+ self.doc.property

	def validate(self):
		"""delete other property setters on this, if this is new"""
		if self.doc.fields['__islocal']:
			webnotes.conn.sql("""delete from `tabProperty Setter` where
				doctype_or_field = %(doctype_or_field)s
				and doc_type = %(doc_type)s
				and ifnull(field_name,'') = ifnull(%(field_name)s, '')
				and property = %(property)s""", self.doc.fields)
				
		# clear cache
		webnotes.clear_cache(doctype = self.doc.doc_type)
	
	def get_property_list(self, dt):
		return webnotes.conn.sql("""select fieldname, label, fieldtype 
		from tabDocField
		where parent=%s
		and fieldtype not in ('Section Break', 'Column Break', 'HTML', 'Read Only', 'Table') 
		and ifnull(fieldname, '') != ''
		order by label asc""", dt, as_dict=1)
		
	def get_setup_data(self):
		return {
			'doctypes': [d[0] for d in webnotes.conn.sql("select name from tabDocType")],
			'dt_properties': self.get_property_list('DocType'),
			'df_properties': self.get_property_list('DocField')
		}
		
	def get_field_ids(self):
		return webnotes.conn.sql("select name, fieldtype, label, fieldname from tabDocField where parent=%s", self.doc.doc_type, as_dict = 1)
	
	def get_defaults(self):
		if not self.doc.field_name:
			return webnotes.conn.sql("select * from `tabDocType` where name=%s", self.doc.doc_type, as_dict = 1)[0]
		else:
			return webnotes.conn.sql("select * from `tabDocField` where fieldname=%s and parent=%s", 
				(self.doc.field_name, self.doc.doc_type), as_dict = 1)[0]
				
	def on_update(self):
		from core.doctype.doctype.doctype import validate_fields_for_doctype
		validate_fields_for_doctype(self.doc.doc_type)