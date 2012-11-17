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

from webnotes.utils import cint, cstr
from webnotes.model.doc import Document
from webnotes import msgprint

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def set_fieldname(self):
		if not self.doc.fieldname:
			# remove special characters from fieldname
			self.doc.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_', cstr(self.doc.label).lower().replace(' ','_'))

	def validate(self):
		from webnotes.model.doctype import get
		self.set_fieldname()
		
		temp_doclist = get(self.doc.dt, form=0)
				
		# set idx
		if not self.doc.idx:
			from webnotes.utils import cint
			max_idx = max(d.idx for d in temp_doclist if d.doctype=='DocField')
			self.doc.idx = cint(max_idx) + 1
		
	def on_update(self):
		# validate field
		from webnotes.utils.cache import CacheItem
		from core.doctype.doctype.doctype import validate_fields_for_doctype

		validate_fields_for_doctype(self.doc.dt)

		CacheItem(self.doc.dt).clear()
				
		# create property setter to emulate insert after
		self.create_property_setter()

		# update the schema
		from webnotes.model.db_schema import updatedb
		updatedb(self.doc.dt)

	def on_trash(self):
		# delete property setter entries
		webnotes.conn.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s""",
				(self.doc.dt, self.doc.fieldname))

		from webnotes.utils.cache import CacheItem
		CacheItem(self.doc.dt).clear()

	def create_property_setter(self):
		idx_label_list, field_list = get_fields_label(self.doc.dt, 0)
		label_index = idx_label_list.index(self.doc.insert_after)
		if label_index==-1: return

		prev_field = field_list[label_index]
		webnotes.conn.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s
			AND property = 'previous_field'""", (self.doc.dt, self.doc.fieldname))
		
		webnotes.model_wrapper([{
			'doctype': "Property Setter",
			'doctype_or_field': 'DocField',
			'doc_type': self.doc.dt,
			'field_name': self.doc.fieldname,
			'property': 'previous_field',
			'value': prev_field,
			'property_type': 'Data',
			'select_doctype': self.doc.dt,
			'__islocal': 1
		}]).save()

@webnotes.whitelist()
def get_fields_label(dt=None, form=1):
	"""
		if form=1: Returns a string of field labels separated by \n
		if form=0: Returns lists of field labels and field names
	"""
	import webnotes
	from webnotes.utils import cstr
	import webnotes.model.doctype
	fieldname = None
	if not dt:
		dt = webnotes.form_dict.get('doctype')
		fieldname = webnotes.form_dict.get('fieldname')
	if not dt: return ""
	
	doclist = webnotes.model.doctype.get(dt, form=0)
	docfields = sorted((d for d in doclist if d.doctype=='DocField'),
			key=lambda d: d.idx)
	
	if fieldname:
		idx_label_list = [cstr(d.label) or cstr(d.fieldname) or cstr(d.fieldtype)
			for d in docfields if d.fieldname != fieldname]
	else:
		idx_label_list = [cstr(d.label) or cstr(d.fieldname) or cstr(d.fieldtype)
			for d in docfields]
	if form:
		return "\n".join(idx_label_list)
	else:
		# return idx_label_list, field_list
		field_list = [cstr(d.fieldname) for d in docfields]
		return idx_label_list, field_list

