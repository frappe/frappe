# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# model __init__.py
from __future__ import unicode_literals
import webnotes

no_value_fields = ['Section Break', 'Column Break', 'HTML', 'Table', 'Button', 'Image']
default_fields = ['doctype','name','owner','creation','modified','modified_by','parent','parentfield','parenttype','idx','docstatus']

def insert(doclist):
	if not isinstance(doclist, list):
		doclist = [doclist]

	for d in doclist:
		if isinstance(d, dict):
			d["__islocal"] = 1
		else:
			d.fields["__islocal"] = 1
		
	wrapper = webnotes.bean(doclist)
	wrapper.save()
	
	return wrapper

@webnotes.whitelist()
def delete_doc(doctype=None, name=None, doclist = None, force=0):
	import webnotes.model.utils
	return webnotes.model.utils.delete_doc(doctype, name, doclist, force)
	
def rename(doctype, old, new, debug=False):
	import webnotes.model.rename_doc
	webnotes.model.rename_doc.rename_doc(doctype, old, new, debug)

def copytables(srctype, src, srcfield, tartype, tar, tarfield, srcfields, tarfields=[]):
	import webnotes.model.doc

	if not tarfields: 
		tarfields = srcfields
	l = []
	data = webnotes.model.doc.getchildren(src.name, srctype, srcfield)
	for d in data:
		newrow = webnotes.model.doc.addchild(tar, tarfield, tartype)
		newrow.idx = d.idx
	
		for i in range(len(srcfields)):
			newrow.fields[tarfields[i]] = d.fields[srcfields[i]]
			
		l.append(newrow)
	return l

def db_exists(dt, dn):
	import webnotes
	return webnotes.conn.exists(dt, dn)

def delete_fields(args_dict, delete=0):
	"""
		Delete a field.
		* Deletes record from `tabDocField`
		* If not single doctype: Drops column from table
		* If single, deletes record from `tabSingles`

		args_dict = { dt: [field names] }
	"""
	import webnotes.utils
	for dt in args_dict.keys():
		fields = args_dict[dt]
		if not fields: continue
		
		webnotes.conn.sql("""\
			DELETE FROM `tabDocField`
			WHERE parent=%s AND fieldname IN (%s)
		""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		
		# Delete the data / column only if delete is specified
		if not delete: continue
		
		is_single = webnotes.conn.sql("select issingle from tabDocType where name = '%s'" % dt)
		is_single = is_single and webnotes.utils.cint(is_single[0][0]) or 0
		if is_single:
			webnotes.conn.sql("""\
				DELETE FROM `tabSingles`
				WHERE doctype=%s AND field IN (%s)
			""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		else:
			existing_fields = webnotes.conn.sql("desc `tab%s`" % dt)
			existing_fields = existing_fields and [e[0] for e in existing_fields] or []
			query = "ALTER TABLE `tab%s` " % dt + \
				", ".join(["DROP COLUMN `%s`" % f for f in fields if f in existing_fields])
			webnotes.conn.commit()
			webnotes.conn.sql(query)
