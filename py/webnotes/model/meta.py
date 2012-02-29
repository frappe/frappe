# metadata

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
	return webnotes.conn.sql("""
		SELECT fieldname, options, label 
		FROM tabDocField 
		WHERE parent='%s' 
		and (fieldtype='Link' or (fieldtype='Select' and `options` like 'link:%%')) 
		and fieldname!='owner'""" % (doctype))

#=================================================================================

def get_table_fields(doctype):
	return webnotes.conn.sql("select options, fieldname from tabDocField \
		where parent='%s' and fieldtype='Table'" % doctype, as_list=1)

	
