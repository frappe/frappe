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

		# create property setter to emulate insert after
		self.create_property_setter()

		from webnotes.utils.cache import CacheItem
		CacheItem(self.doc.dt).clear()

	def on_trash(self):
		# delete property setter entries
		webnotes.conn.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND (doc_name = %s
			OR (property = 'previous_field' AND value = %s))""",
				(self.doc.dt, self.doc.name, self.doc.name))

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
		ps = Document('Property Setter', fielddata = {
			'doctype_or_field': 'DocField',
			'doc_type': self.doc.dt,
			'field_name': self.doc.fieldname,
			'property': 'previous_field',
			'value': prev_field,
			'property_type': 'Data',
			'select_doctype': self.doc.dt
		})
		ps.save(1)


@webnotes.whitelist()
def get_fields_label(dt=None, form=1):
	"""
		if form=1: Returns a string of field labels separated by \n
		if form=0: Returns lists of field labels and field names
	"""
	import webnotes
	from webnotes.utils import cstr
	import webnotes.model.doctype
	
	if not dt: dt = webnotes.form_dict.get('doctype')
	if not dt: return ""
	
	doclist = webnotes.model.doctype.get(dt, form=0)
	docfields = sorted((d for d in doclist if d.doctype=='DocField'),
			key=lambda d: d.idx)
	idx_label_list = (" - ".join([cstr(d.label) or cstr(d.fieldname) or \
		cstr(d.fieldtype), cstr(d.idx)]) for d in docfields)
	if form:
		return "\n".join(idx_label_list)
	else:
		# return idx_label_list, field_list
		field_list = [cstr(d.fieldname) for d in docfields]
		return list(idx_label_list), field_list

