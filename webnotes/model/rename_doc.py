# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _
from webnotes.utils import cint
import webnotes.model.doctype
from webnotes.model.doc import validate_name

@webnotes.whitelist()
def rename_doc(doctype, old, new, force=False, merge=False):
	"""
		Renames a doc(dt, old) to doc(dt, new) and 
		updates all linked fields of type "Link" or "Select" with "link:"
	"""
	if not webnotes.conn.exists(doctype, old):
		return
	
	force = cint(force)
	merge = cint(merge)
	
	# get doclist of given doctype
	doclist = webnotes.model.doctype.get(doctype)
	
	# call on_rename
	obj = webnotes.get_obj(doctype, old)
	if hasattr(obj, 'on_rename'):
		new = obj.on_rename(new, old, merge) or new
		
	new = validate_rename(doctype, new, doclist, merge, force)
		
	if not merge:
		rename_parent_and_child(doctype, old, new, doclist)
			
	# update link fields' values
	link_fields = get_link_fields(doctype)
	update_link_field_values(link_fields, old, new)
	
	if doctype=='DocType':
		rename_doctype(doctype, old, new, force)
	
	update_attachments(doctype, old, new)
	
	if merge:
		webnotes.delete_doc(doctype, old)
		
	return new

def update_attachments(doctype, old, new):
	try:
		webnotes.conn.sql("""update `tabFile Data` set attached_to_name=%s
			where attached_to_name=%s and attached_to_doctype=%s""", (new, old, doctype))
	except Exception, e:
		if e.args[0]!=1054: # in patch?
			raise 

def rename_parent_and_child(doctype, old, new, doclist):
	# rename the doc
	webnotes.conn.sql("update `tab%s` set name=%s where name=%s" \
		% (doctype, '%s', '%s'), (new, old))

	update_child_docs(old, new, doclist)

def validate_rename(doctype, new, doclist, merge, force):
	exists = webnotes.conn.exists(doctype, new)

	if merge and not exists:
		webnotes.msgprint("%s: %s does not exist, select a new target to merge." % (doctype, new), raise_exception=1)
	
	if (not merge) and exists:
		webnotes.msgprint("%s: %s exists, select a new, new name." % (doctype, new), raise_exception=1)

	if not webnotes.has_permission(doctype, "write"):
		webnotes.msgprint("You need write permission to rename", raise_exception=1)

	if not force and not doclist[0].allow_rename:
		webnotes.msgprint("%s cannot be renamed" % doctype, raise_exception=1)
	
	# validate naming like it's done in doc.py
	new = validate_name(doctype, new, merge=merge)

	return new

def rename_doctype(doctype, old, new, force=False):
	# change options for fieldtype Table
	update_parent_of_fieldtype_table(old, new)
	
	# change options where select options are hardcoded i.e. listed
	select_fields = get_select_fields(old, new)
	update_link_field_values(select_fields, old, new)
	update_select_field_values(old, new)
	
	# change parenttype for fieldtype Table
	update_parenttype_values(old, new)
	
	# rename comments
	webnotes.conn.sql("""update tabComment set comment_doctype=%s where comment_doctype=%s""",
		(new, old))

def update_child_docs(old, new, doclist):
	# update "parent"
	child_doctypes = (d.options for d in doclist 
		if d.doctype=='DocField' and d.fieldtype=='Table')
	
	for child in child_doctypes:
		webnotes.conn.sql("update `tab%s` set parent=%s where parent=%s" \
			% (child, '%s', '%s'), (new, old))

def update_link_field_values(link_fields, old, new):
	update_list = []
	
	# update values
	for field in link_fields:
		# if already updated, do not do it again
		if [field['parent'], field['fieldname']] in update_list:
			continue
		update_list.append([field['parent'], field['fieldname']])
		if field['issingle']:
			webnotes.conn.sql("""\
				update `tabSingles` set value=%s
				where doctype=%s and field=%s and value=%s""",
				(new, field['parent'], field['fieldname'], old))
		else:
			webnotes.conn.sql("""\
				update `tab%s` set `%s`=%s
				where `%s`=%s""" \
				% (field['parent'], field['fieldname'], '%s',
					field['fieldname'], '%s'),
				(new, old))
			
def get_link_fields(doctype):
	# get link fields from tabDocField
	link_fields = webnotes.conn.sql("""\
		select parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.parent not like "old%%%%" and df.parent != '0' and
			((df.options=%s and df.fieldtype='Link') or
			(df.options='link:%s' and df.fieldtype='Select'))""" \
		% ('%s', doctype), doctype, as_dict=1)
	
	# get link fields from tabCustom Field
	custom_link_fields = webnotes.conn.sql("""\
		select dt as parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.dt not like "old%%%%" and df.dt != '0' and
			((df.options=%s and df.fieldtype='Link') or
			(df.options='link:%s' and df.fieldtype='Select'))""" \
		% ('%s', doctype), doctype, as_dict=1)
	
	# add custom link fields list to link fields list
	link_fields += custom_link_fields
	
	# remove fields whose options have been changed using property setter
	property_setter_link_fields = webnotes.conn.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.property_type='options' and
			ps.field_name is not null and
			(ps.value=%s or ps.value='link:%s')""" \
		% ('%s', doctype), doctype, as_dict=1)
		
	link_fields += property_setter_link_fields
	
	return link_fields
	
def update_parent_of_fieldtype_table(old, new):
	webnotes.conn.sql("""\
		update `tabDocField` set options=%s
		where fieldtype='Table' and options=%s""", (new, old))
	
	webnotes.conn.sql("""\
		update `tabCustom Field` set options=%s
		where fieldtype='Table' and options=%s""", (new, old))
		
	webnotes.conn.sql("""\
		update `tabProperty Setter` set value=%s
		where property='options' and value=%s""", (new, old))
		
def get_select_fields(old, new):
	"""
		get select type fields where doctype's name is hardcoded as
		new line separated list
	"""
	# get link fields from tabDocField
	select_fields = webnotes.conn.sql("""\
		select parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.parent not like "old%%%%" and df.parent != '0' and
			df.parent != %s and df.fieldtype = 'Select' and
			df.options not like "link:%%%%" and
			(df.options like "%%%%%s%%%%")""" \
		% ('%s', old), new, as_dict=1)
	
	# get link fields from tabCustom Field
	custom_select_fields = webnotes.conn.sql("""\
		select dt as parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.dt not like "old%%%%" and df.dt != '0' and
			df.dt != %s and df.fieldtype = 'Select' and
			df.options not like "link:%%%%" and
			(df.options like "%%%%%s%%%%")""" \
		% ('%s', old), new, as_dict=1)
	
	# add custom link fields list to link fields list
	select_fields += custom_select_fields
	
	# remove fields whose options have been changed using property setter
	property_setter_select_fields = webnotes.conn.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.doc_type != %s and
			ps.property_type='options' and
			ps.field_name is not null and
			ps.value not like "link:%%%%" and
			(ps.value like "%%%%%s%%%%")""" \
		% ('%s', old), new, as_dict=1)
		
	select_fields += property_setter_select_fields
	
	return select_fields
	
def update_select_field_values(old, new):
	webnotes.conn.sql("""\
		update `tabDocField` set options=replace(options, %s, %s)
		where
			parent != %s and parent not like "old%%%%" and
			fieldtype = 'Select' and options not like "link:%%%%" and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))

	webnotes.conn.sql("""\
		update `tabCustom Field` set options=replace(options, %s, %s)
		where
			dt != %s and dt not like "old%%%%" and
			fieldtype = 'Select' and options not like "link:%%%%" and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))

	webnotes.conn.sql("""\
		update `tabProperty Setter` set value=replace(value, %s, %s)
		where
			doc_type != %s and field_name is not null and
			property='options' and value not like "link%%%%" and
			(value like "%%%%\\n%s%%%%" or value like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))
		
def update_parenttype_values(old, new):
	child_doctypes = webnotes.conn.sql("""\
		select options, fieldname from `tabDocField`
		where parent=%s and fieldtype='Table'""", new, as_dict=1)

	custom_child_doctypes = webnotes.conn.sql("""\
		select options, fieldname from `tabCustom Field`
		where dt=%s and fieldtype='Table'""", new, as_dict=1)

	child_doctypes += custom_child_doctypes
	fields = [d['fieldname'] for d in child_doctypes]
	
	property_setter_child_doctypes = webnotes.conn.sql("""\
		select value as options from `tabProperty Setter`
		where doc_type=%s and property='options' and
		field_name in ("%s")""" % ('%s', '", "'.join(fields)),
		new)
		
	child_doctypes += property_setter_child_doctypes
	child_doctypes = (d['options'] for d in child_doctypes)
		
	for doctype in child_doctypes:
		webnotes.conn.sql("""\
			update `tab%s` set parenttype=%s
			where parenttype=%s""" % (doctype, '%s', '%s'),
		(new, old))