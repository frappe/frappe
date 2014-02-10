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

def rename_field(doctype, old_fieldname, new_fieldname):
	"""This functions assumes that doctype is already synced"""
	
	doctype_list = webnotes.get_doctype(doctype)
	new_field = doctype_list.get_field(new_fieldname)
	if not new_field:
		print "rename_field: " + (new_fieldname) + " not found in " + doctype
		return
	
	if new_field.fieldtype == "Table":
		# change parentfield of table mentioned in options
		webnotes.conn.sql("""update `tab%s` set parentfield=%s
			where parentfield=%s""" % (new_field.options.split("\n")[0], "%s", "%s"),
			(new_fieldname, old_fieldname))
	elif new_field.fieldtype not in no_value_fields:
		if doctype_list[0].issingle:
			webnotes.conn.sql("""update `tabSingles` set field=%s
				where doctype=%s and field=%s""", 
				(new_fieldname, doctype, old_fieldname))
		else:
			webnotes.conn.sql("""update `tab%s` set `%s`=`%s`""" % \
				(doctype, new_fieldname, old_fieldname))
				
	webnotes.conn.sql("""update `tabProperty Setter` set field_name = %s 
		where doc_type=%s and field_name=%s""", (new_fieldname, doctype, old_fieldname))
		
	import json
	user_report_cols = webnotes.conn.sql("""select defkey, defvalue from `tabDefaultValue` where 
		defkey like '_list_settings:%'""")
	for key, value in user_report_cols:
		new_columns = []
		columns_modified = False
		for field, field_doctype in json.loads(value):
			if field == old_fieldname and field_doctype == doctype:
				new_columns.append([field, field_doctype])
				columns_modified=True
		if columns_modified:
			webnotes.conn.sql("""update `tabDefaultValue` set defvalue=%s 
				where defkey=%s""" % ('%s', '%s'), (json.dumps(new_columns), key))