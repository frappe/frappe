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

# metadata

from __future__ import unicode_literals
import webnotes
	
#=================================================================================

def get_dt_values(doctype, fields, as_dict = 0):
	return webnotes.conn.sql('SELECT %s FROM tabDocType WHERE name="%s"' % (fields, doctype), as_dict = as_dict)

def set_dt_value(doctype, field, value):
	return webnotes.conn.set_value('DocType', doctype, field, value)

def is_single(doctype):
	try:
		return get_dt_values(doctype, 'issingle')[0][0]
	except IndexError, e:
		raise Exception, 'Cannot determine whether %s is single' % doctype

#=================================================================================

def get_parent_dt(dt):
	parent_dt = webnotes.conn.sql("""select parent from tabDocField 
		where fieldtype="Table" and options="%s" and (parent not like "old_parent:%%") 
		limit 1""" % dt)
	return parent_dt and parent_dt[0][0] or ''

#=================================================================================

def set_fieldname(field_id, fieldname):
	webnotes.conn.set_value('DocField', field_id, 'fieldname', fieldname)

#=================================================================================

def get_link_fields(doctype):
	"""
		Returns list of link fields for a doctype in tuple (fieldname, options, label)
	"""
	import webnotes.model.doctype
	doclist = webnotes.model.doctype.get(doctype)
	return [
		(d.fields.get('fieldname'), d.fields.get('options'), d.fields.get('label'))
		for d in doclist
		if d.fields.get('doctype') == 'DocField' and d.fields.get('parent') == doctype
		and d.fields.get('fieldname')!='owner'
		and (d.fields.get('fieldtype') == 'Link' or
			(	d.fields.get('fieldtype') == 'Select'
				and (d.fields.get('options') or '').startswith('link:'))
			)
	]

#=================================================================================

def get_table_fields(doctype):
	child_tables = [[d[0], d[1]] for d in webnotes.conn.sql("select options, fieldname from tabDocField \
		where parent='%s' and fieldtype='Table'" % doctype, as_list=1)]
	
	custom_child_tables = [[d[0], d[1]] for d in webnotes.conn.sql("select options, fieldname from `tabCustom Field` \
		where dt='%s' and fieldtype='Table'" % doctype, as_list=1)]

	return child_tables + custom_child_tables
