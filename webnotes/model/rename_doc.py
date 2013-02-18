from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def rename_doc(doctype, old, new, debug=0, force=False):
	"""
		Renames a doc(dt, old) to doc(dt, new) and 
		updates all linked fields of type "Link" or "Select" with "link:"
	"""
	import webnotes.utils
	import webnotes.model.doctype
	from webnotes.model.code import get_obj

	# get doclist of given doctype
	doclist = webnotes.model.doctype.get(doctype)
	
	if webnotes.conn.exists(doctype, new):
		webnotes.msgprint("%s: %s exists, select a new, new name." % (doctype, new))

	if not webnotes.has_permission(doctype, "write"):
		webnotes.msgprint("You need write permission to rename", raise_exception=1)

	if not force and not doclist[0].allow_rename:
		webnotes.msgprint("%s cannot be renamed" % doctype, raise_exception=1)
	
	# without child fields of table type fields (form=0)
	# call on_rename method if exists
	obj = get_obj(doctype, old)
	if hasattr(obj, 'on_rename'):
		new = obj.on_rename(new, old) or new
		
	# rename the doc
	webnotes.conn.sql("update `tab%s` set name=%s where name=%s" \
		% (doctype, '%s', '%s'), (new, old), debug=debug)
	
	update_child_docs(old, new, doclist, debug=debug)
	if debug: webnotes.errprint("executed update_child_docs")
	
	if doctype=='DocType':
		# rename the table or change doctype of singles
		issingle = webnotes.conn.sql("""\
			select ifnull(issingle, 0) from `tabDocType`
			where name=%s""", new)

		if issingle and webnotes.utils.cint(issingle[0][0]) or 0:
			webnotes.conn.sql("""\
				update tabSingles set doctype=%s
				where doctype=%s""", (new, old))
		else:
			webnotes.conn.sql("rename table `tab%s` to `tab%s`" % (old, new))
		if debug: webnotes.errprint("executed rename table")
	
	# update link fields' values
	link_fields = get_link_fields(doctype)
	if debug: webnotes.errprint(link_fields)
	update_link_field_values(link_fields, old, new, debug=debug)
	if debug: webnotes.errprint("executed update_link_field_values")
	
	if doctype=='DocType':
		rename_doctype(doctype, old, new, debug, force)
		
	return new
	
def rename_doctype(doctype, old, new, debug=0, force=False):
	# change options for fieldtype Table
	update_parent_of_fieldtype_table(old, new, debug=debug)
	if debug: webnotes.errprint("executed update_parent_of_fieldtype_table")
	
	# change options where select options are hardcoded i.e. listed
	select_fields = get_select_fields(old, new, debug=debug)
	update_link_field_values(select_fields, old, new, debug=debug)
	if debug: webnotes.errprint("executed update_link_field_values")
	update_select_field_values(old, new, debug=debug)
	if debug: webnotes.errprint("executed update_select_field_values")
	
	# change parenttype for fieldtype Table
	update_parenttype_values(old, new, debug=debug)
	if debug: webnotes.errprint("executed update_parenttype_values")
	
	# update mapper
	rename_mapper(new)
	
def rename_mapper(new):
	for mapper in webnotes.conn.sql("""select name, from_doctype, to_doctype 
			from `tabDocType Mapper` where from_doctype=%s or to_doctype=%s""", (new, new), as_dict=1):
		rename_doc("DocType Mapper", mapper.name, mapper.from_doctype + "-" + mapper.to_doctype, force=True)
		
def update_child_docs(old, new, doclist, debug=0):
	"""
		updates 'parent' field of child documents
	"""
	# generator of a list of child doctypes
	child_doctypes = (d.options for d in doclist 
		if d.doctype=='DocField' and d.fieldtype=='Table')
	
	for child in child_doctypes:
		webnotes.conn.sql("update `tab%s` set parent=%s where parent=%s" \
			% (child, '%s', '%s'), (new, old), debug=debug)

def update_link_field_values(link_fields, old, new, debug=0):
	"""
		updates values in tables where current doc is stored as a 
		link field or select field
	"""	
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
				(new, field['parent'], field['fieldname'], old),
				debug=debug)
		else:
			webnotes.conn.sql("""\
				update `tab%s` set `%s`=%s
				where `%s`=%s""" \
				% (field['parent'], field['fieldname'], '%s',
					field['fieldname'], '%s'),
				(new, old),
				debug=debug)
			
def get_link_fields(doctype, debug=0):
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
		% ('%s', doctype), doctype, as_dict=1, debug=debug)
	
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
		% ('%s', doctype), doctype, as_dict=1, debug=debug)
	
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
		% ('%s', doctype), doctype, as_dict=1, debug=debug)
		
	link_fields += property_setter_link_fields
	
	return link_fields
	
def update_parent_of_fieldtype_table(old, new, debug=0):
	webnotes.conn.sql("""\
		update `tabDocField` set options=%s
		where fieldtype='Table' and options=%s""", (new, old), debug=debug)
	
	webnotes.conn.sql("""\
		update `tabCustom Field` set options=%s
		where fieldtype='Table' and options=%s""", (new, old), debug=debug)
		
	webnotes.conn.sql("""\
		update `tabProperty Setter` set value=%s
		where property='options' and value=%s""", (new, old), debug=debug)
		
def get_select_fields(old, new, debug=0):
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
		% ('%s', old), new, as_dict=1, debug=debug)
	
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
		% ('%s', old), new, as_dict=1, debug=debug)
	
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
		% ('%s', old), new, as_dict=1, debug=debug)
		
	select_fields += property_setter_select_fields
	
	return select_fields
	
def update_select_field_values(old, new, debug=0):
	webnotes.conn.sql("""\
		update `tabDocField` set options=replace(options, %s, %s)
		where
			parent != %s and parent not like "old%%%%" and
			fieldtype = 'Select' and options not like "link:%%%%" and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new), debug=debug)

	webnotes.conn.sql("""\
		update `tabCustom Field` set options=replace(options, %s, %s)
		where
			dt != %s and dt not like "old%%%%" and
			fieldtype = 'Select' and options not like "link:%%%%" and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new), debug=debug)

	webnotes.conn.sql("""\
		update `tabProperty Setter` set value=replace(value, %s, %s)
		where
			doc_type != %s and field_name is not null and
			property='options' and value not like "link%%%%" and
			(value like "%%%%\\n%s%%%%" or value like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new), debug=debug)
		
def update_parenttype_values(old, new, debug=0):
	child_doctypes = webnotes.conn.sql("""\
		select options, fieldname from `tabDocField`
		where parent=%s and fieldtype='Table'""", new, as_dict=1, debug=debug)

	custom_child_doctypes = webnotes.conn.sql("""\
		select options, fieldname from `tabCustom Field`
		where dt=%s and fieldtype='Table'""", new, as_dict=1, debug=debug)

	child_doctypes += custom_child_doctypes
	fields = [d['fieldname'] for d in child_doctypes]
	
	property_setter_child_doctypes = webnotes.conn.sql("""\
		select value as options from `tabProperty Setter`
		where doc_type=%s and property='options' and
		field_name in ("%s")""" % ('%s', '", "'.join(fields)),
		new, debug=debug)
		
	child_doctypes += property_setter_child_doctypes
	child_doctypes = (d['options'] for d in child_doctypes)
		
	for doctype in child_doctypes:
		webnotes.conn.sql("""\
			update `tab%s` set parenttype=%s
			where parenttype=%s""" % (doctype, '%s', '%s'),
		(new, old), debug=debug)