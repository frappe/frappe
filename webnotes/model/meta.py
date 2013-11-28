# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# metadata

from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr, cint
	
def is_single(doctype):
	try:
		return webnotes.conn.get_value("DocType", doctype, "issingle")
	except IndexError, e:
		raise Exception, 'Cannot determine whether %s is single' % doctype

def get_parent_dt(dt):
	parent_dt = webnotes.conn.sql("""select parent from tabDocField 
		where fieldtype="Table" and options="%s" and (parent not like "old_parent:%%") 
		limit 1""" % dt)
	return parent_dt and parent_dt[0][0] or ''

def set_fieldname(field_id, fieldname):
	webnotes.conn.set_value('DocField', field_id, 'fieldname', fieldname)

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

def get_table_fields(doctype):
	child_tables = [[d[0], d[1]] for d in webnotes.conn.sql("select options, fieldname from tabDocField \
		where parent='%s' and fieldtype='Table'" % doctype, as_list=1)]
	
	try:
		custom_child_tables = [[d[0], d[1]] for d in webnotes.conn.sql("select options, fieldname from `tabCustom Field` \
			where dt='%s' and fieldtype='Table'" % doctype, as_list=1)]
	except Exception, e:
		if e.args[0]!=1146:
			raise
		custom_child_tables = []

	return child_tables + custom_child_tables

def has_field(doctype, fieldname, parent=None, parentfield=None):
	return get_field(doctype, fieldname, parent=None, parentfield=None) and True or False
		
def get_field(doctype, fieldname, parent=None, parentfield=None):
	doclist = webnotes.get_doctype(doctype)
	return doclist.get_field(fieldname, parent, parentfield)
	
def get_field_currency(df, doc):
	"""get currency based on DocField options and fieldvalue in doc"""
	currency = None
	
	if ":" in cstr(df.options):
		split_opts = df.options.split(":")
		if len(split_opts)==3:
			currency = webnotes.conn.get_value(split_opts[0], doc.fields.get(split_opts[1]), 
				split_opts[2])
	else:
		currency = doc.fields.get(df.options)

	return currency
	
def get_field_precision(df, doc):
	"""get precision based on DocField options and fieldvalue in doc"""
	from webnotes.utils import get_number_format_info
	
	number_format = None
	if df.fieldtype == "Currency":
		currency = get_field_currency(df, doc)
		if currency:
			number_format = webnotes.conn.get_value("Currency", currency, "number_format")
		
	if not number_format:
		number_format = webnotes.conn.get_default("number_format") or "#,###.##"
		
	decimal_str, comma_str, precision = get_number_format_info(number_format)

	if df.fieldtype == "Float":
		precision = cint(webnotes.conn.get_default("float_precision")) or 3

	return precision