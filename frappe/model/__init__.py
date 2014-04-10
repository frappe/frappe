# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# model __init__.py
from __future__ import unicode_literals
import frappe

no_value_fields = ['Section Break', 'Column Break', 'HTML', 'Table', 'Button', 'Image']
default_fields = ['doctype','name','owner','creation','modified','modified_by','parent','parentfield','parenttype','idx','docstatus']
integer_docfield_properties = ["reqd", "search_index", "in_list_view", "permlevel", "hidden", "read_only", "ignore_restrictions", "allow_on_submit", "report_hide", "in_filter", "no_copy", "print_hide"]

def insert(doclist):
	if not isinstance(doclist, list):
		doclist = [doclist]

	for d in doclist:
		if isinstance(d, dict):
			d["__islocal"] = 1
		else:
			d.set("__islocal", 1)
		
	wrapper = frappe.get_doc(doclist)
	wrapper.save()
	
	return wrapper

def rename(doctype, old, new, debug=False):
	import frappe.model.rename_doc
	frappe.model.rename_doc.rename_doc(doctype, old, new, debug)

def copytables(srctype, src, srcfield, tartype, tar, tarfield, srcfields, tarfields=[]):
	if not tarfields: 
		tarfields = srcfields
	l = []
	data = src.get(srcfield)
	for d in data:
		newrow = tar.append(tarfield)
		newrow.idx = d.idx
	
		for i in range(len(srcfields)):
			newrow.set(tarfields[i], d.get(srcfields[i]))
			
		l.append(newrow)
	return l

def db_exists(dt, dn):
	import frappe
	return frappe.db.exists(dt, dn)

def delete_fields(args_dict, delete=0):
	"""
		Delete a field.
		* Deletes record from `tabDocField`
		* If not single doctype: Drops column from table
		* If single, deletes record from `tabSingles`

		args_dict = { dt: [field names] }
	"""
	import frappe.utils
	for dt in args_dict.keys():
		fields = args_dict[dt]
		if not fields: continue
		
		frappe.db.sql("""\
			DELETE FROM `tabDocField`
			WHERE parent=%s AND fieldname IN (%s)
		""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		
		# Delete the data / column only if delete is specified
		if not delete: continue
		
		if frappe.db.get_value("DocType", dt, "issingle"):
			frappe.db.sql("""\
				DELETE FROM `tabSingles`
				WHERE doctype=%s AND field IN (%s)
			""" % ('%s', ", ".join(['"' + f + '"' for f in fields])), dt)
		else:
			existing_fields = frappe.db.sql("desc `tab%s`" % dt)
			existing_fields = existing_fields and [e[0] for e in existing_fields] or []
			query = "ALTER TABLE `tab%s` " % dt + \
				", ".join(["DROP COLUMN `%s`" % f for f in fields if f in existing_fields])
			frappe.db.commit()
			frappe.db.sql(query)

def rename_field(doctype, old_fieldname, new_fieldname):
	"""This functions assumes that doctype is already synced"""
	
	meta = frappe.get_meta(doctype)
	new_field = meta.get_field(new_fieldname)
	if not new_field:
		print "rename_field: " + (new_fieldname) + " not found in " + doctype
		return
	
	if new_field.fieldtype == "Table":
		# change parentfield of table mentioned in options
		frappe.db.sql("""update `tab%s` set parentfield=%s
			where parentfield=%s""" % (new_field.options.split("\n")[0], "%s", "%s"),
			(new_fieldname, old_fieldname))
	elif new_field.fieldtype not in no_value_fields:
		if meta.issingle:
			frappe.db.sql("""update `tabSingles` set field=%s
				where doctype=%s and field=%s""", 
				(new_fieldname, doctype, old_fieldname))
		else:
			# copy field value
			frappe.db.sql("""update `tab%s` set `%s`=`%s`""" % \
				(doctype, new_fieldname, old_fieldname))
	
	# update in property setter
	frappe.db.sql("""update `tabProperty Setter` set field_name = %s 
		where doc_type=%s and field_name=%s""", (new_fieldname, doctype, old_fieldname))
		
	update_users_report_view_settings(doctype, old_fieldname)
		
def update_users_report_view_settings(doctype, ref_fieldname):
	import json
	user_report_cols = frappe.db.sql("""select defkey, defvalue from `tabDefaultValue` where 
		defkey like '_list_settings:%'""")
	for key, value in user_report_cols:
		new_columns = []
		columns_modified = False
		for field, field_doctype in json.loads(value):
			if field == ref_fieldname and field_doctype == doctype:
				new_columns.append([field, field_doctype])
				columns_modified=True
		if columns_modified:
			frappe.db.sql("""update `tabDefaultValue` set defvalue=%s 
				where defkey=%s""" % ('%s', '%s'), (json.dumps(new_columns), key))