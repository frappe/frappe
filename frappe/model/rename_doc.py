# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.naming import validate_name

@frappe.whitelist()
def rename_doc(doctype, old, new, force=False, merge=False, ignore_permissions=False):
	"""
		Renames a doc(dt, old) to doc(dt, new) and
		updates all linked fields of type "Link"
	"""
	if not frappe.db.exists(doctype, old):
		return

	force = cint(force)
	merge = cint(merge)

	meta = frappe.get_meta(doctype)

	# call before_rename
	old_doc = frappe.get_doc(doctype, old)
	out = old_doc.run_method("before_rename", old, new, merge) or {}
	new = (out.get("new") or new) if isinstance(out, dict) else (out or new)
	new = validate_rename(doctype, new, meta, merge, force, ignore_permissions)

	if not merge:
		rename_parent_and_child(doctype, old, new, meta)

	# update link fields' values
	link_fields = get_link_fields(doctype)
	update_link_field_values(link_fields, old, new, doctype)

	rename_dynamic_links(doctype, old, new)

	if doctype=='DocType':
		rename_doctype(doctype, old, new, force)

	update_comments(doctype, old, new, force)
	update_attachments(doctype, old, new)

	if merge:
		frappe.delete_doc(doctype, old)

	# call after_rename
	new_doc = frappe.get_doc(doctype, new)

	# copy any flags if required
	new_doc._local = getattr(old_doc, "_local", None)

	new_doc.run_method("after_rename", old, new, merge)

	rename_versions(doctype, old, new)

	# update user_permissions
	frappe.db.sql("""update tabDefaultValue set defvalue=%s where parenttype='User Permission'
		and defkey=%s and defvalue=%s""", (new, doctype, old))
	frappe.clear_cache()

	return new

def update_attachments(doctype, old, new):
	try:
		frappe.db.sql("""update `tabFile Data` set attached_to_name=%s
			where attached_to_name=%s and attached_to_doctype=%s""", (new, old, doctype))
	except Exception, e:
		if e.args[0]!=1054: # in patch?
			raise

def rename_versions(doctype, old, new):
	frappe.db.sql("""update tabVersion set docname=%s where ref_doctype=%s and docname=%s""",
		(new, doctype, old))

def rename_parent_and_child(doctype, old, new, meta):
	# rename the doc
	frappe.db.sql("update `tab%s` set name=%s where name=%s" \
		% (doctype, '%s', '%s'), (new, old))

	update_child_docs(old, new, meta)

def validate_rename(doctype, new, meta, merge, force, ignore_permissions):
	exists = frappe.db.get_value(doctype, new)

	if merge and not exists:
		frappe.msgprint(_("{0} {1} does not exist, select a new target to merge").format(doctype, new), raise_exception=1)

	if (not merge) and exists == new:
		frappe.msgprint(_("Another {0} with name {1} exists, select another name").format(doctype, new), raise_exception=1)

	if not (ignore_permissions or frappe.has_permission(doctype, "write")):
		frappe.msgprint(_("You need write permission to rename"), raise_exception=1)

	if not force and not meta.allow_rename:
		frappe.msgprint(_("{0} not allowed to be renamed").format(_(doctype)), raise_exception=1)

	# validate naming like it's done in doc.py
	new = validate_name(doctype, new, merge=merge)

	return new

def rename_doctype(doctype, old, new, force=False):
	# change options for fieldtype Table
	update_options_for_fieldtype("Table", old, new)
	update_options_for_fieldtype("Link", old, new)

	# change options where select options are hardcoded i.e. listed
	select_fields = get_select_fields(old, new)
	update_link_field_values(select_fields, old, new, doctype)
	update_select_field_values(old, new)

	# change parenttype for fieldtype Table
	update_parenttype_values(old, new)

	# rename comments
	frappe.db.sql("""update tabComment set comment_doctype=%s where comment_doctype=%s""",
		(new, old))

def update_comments(doctype, old, new, force=False):
	frappe.db.sql("""update `tabComment` set comment_docname=%s
		where comment_doctype=%s and comment_docname=%s""", (new, doctype, old))

def update_child_docs(old, new, meta):
	# update "parent"
	for df in meta.get_table_fields():
		frappe.db.sql("update `tab%s` set parent=%s where parent=%s" \
			% (df.options, '%s', '%s'), (new, old))

def update_link_field_values(link_fields, old, new, doctype):
	for field in link_fields:
		if field['issingle']:
			frappe.db.sql("""\
				update `tabSingles` set value=%s
				where doctype=%s and field=%s and value=%s""",
				(new, field['parent'], field['fieldname'], old))
		else:
			if field['parent']!=new:
				frappe.db.sql("""\
					update `tab%s` set `%s`=%s
					where `%s`=%s""" \
					% (field['parent'], field['fieldname'], '%s',
						field['fieldname'], '%s'),
					(new, old))

def get_link_fields(doctype):
	# get link fields from tabDocField
	link_fields = frappe.db.sql("""\
		select parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.options=%s and df.fieldtype='Link'""", (doctype,), as_dict=1)

	# get link fields from tabCustom Field
	custom_link_fields = frappe.db.sql("""\
		select dt as parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.options=%s and df.fieldtype='Link'""", (doctype,), as_dict=1)

	# add custom link fields list to link fields list
	link_fields += custom_link_fields

	# remove fields whose options have been changed using property setter
	property_setter_link_fields = frappe.db.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.property_type='options' and
			ps.field_name is not null and
			ps.value=%s""", (doctype,), as_dict=1)

	link_fields += property_setter_link_fields

	return link_fields

def update_options_for_fieldtype(fieldtype, old, new):
	frappe.db.sql("""update `tabDocField` set options=%s
		where fieldtype=%s and options=%s""", (new, fieldtype, old))

	frappe.db.sql("""update `tabCustom Field` set options=%s
		where fieldtype=%s and options=%s""", (new, fieldtype, old))

	frappe.db.sql("""update `tabProperty Setter` set value=%s
		where property='options' and value=%s""", (new, old))

def get_select_fields(old, new):
	"""
		get select type fields where doctype's name is hardcoded as
		new line separated list
	"""
	# get link fields from tabDocField
	select_fields = frappe.db.sql("""\
		select parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.parent != %s and df.fieldtype = 'Select' and
			df.options like "%%%%%s%%%%" """ \
		% ('%s', old), (new,), as_dict=1)

	# get link fields from tabCustom Field
	custom_select_fields = frappe.db.sql("""\
		select dt as parent, fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.dt != %s and df.fieldtype = 'Select' and
			df.options like "%%%%%s%%%%" """ \
		% ('%s', old), (new,), as_dict=1)

	# add custom link fields list to link fields list
	select_fields += custom_select_fields

	# remove fields whose options have been changed using property setter
	property_setter_select_fields = frappe.db.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select ifnull(issingle, 0) from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.doc_type != %s and
			ps.property_type='options' and
			ps.field_name is not null and
			ps.value like "%%%%%s%%%%" """ \
		% ('%s', old), (new,), as_dict=1)

	select_fields += property_setter_select_fields

	return select_fields

def update_select_field_values(old, new):
	frappe.db.sql("""\
		update `tabDocField` set options=replace(options, %s, %s)
		where
			parent != %s and fieldtype = 'Select' and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))

	frappe.db.sql("""\
		update `tabCustom Field` set options=replace(options, %s, %s)
		where
			dt != %s and fieldtype = 'Select' and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))

	frappe.db.sql("""\
		update `tabProperty Setter` set value=replace(value, %s, %s)
		where
			doc_type != %s and field_name is not null and
			property='options' and
			(value like "%%%%\\n%s%%%%" or value like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', old, old), (old, new, new))

def update_parenttype_values(old, new):
	child_doctypes = frappe.db.sql("""\
		select options, fieldname from `tabDocField`
		where parent=%s and fieldtype='Table'""", (new,), as_dict=1)

	custom_child_doctypes = frappe.db.sql("""\
		select options, fieldname from `tabCustom Field`
		where dt=%s and fieldtype='Table'""", (new,), as_dict=1)

	child_doctypes += custom_child_doctypes
	fields = [d['fieldname'] for d in child_doctypes]

	property_setter_child_doctypes = frappe.db.sql("""\
		select value as options from `tabProperty Setter`
		where doc_type=%s and property='options' and
		field_name in ("%s")""" % ('%s', '", "'.join(fields)),
		(new,))

	child_doctypes += property_setter_child_doctypes
	child_doctypes = (d['options'] for d in child_doctypes)

	for doctype in child_doctypes:
		frappe.db.sql("""\
			update `tab%s` set parenttype=%s
			where parenttype=%s""" % (doctype, '%s', '%s'),
		(new, old))

dynamic_link_queries =  [
	"""select parent, fieldname, options from tabDocField where fieldtype='Dynamic Link'""",
	"""select dt as parent, fieldname, options from `tabCustom Field` where fieldtype='Dynamic Link'""",
]

def rename_dynamic_links(doctype, old, new):
	for query in dynamic_link_queries:
		for df in frappe.db.sql(query, as_dict=True):

			# dynamic link in single, just one value to check
			if frappe.get_meta(df.parent).issingle:
				refdoc = frappe.db.get_singles_dict(df.parent)
				if refdoc.get(df.options)==doctype and refdoc.get(df.fieldname)==old:

					frappe.db.sql("""update tabSingles set value=%s where
						field=%s and value=%s and doctype=%s""", (new, df.fieldname, old, df.parent))
			else:
				# replace for each value where renamed
				for to_change in frappe.db.sql_list("""select name from `tab{parent}` where
					{options}=%s and {fieldname}=%s""".format(**df), (doctype, old)):

					frappe.db.sql("""update `tab{parent}` set {fieldname}=%s
						where name=%s""".format(**df), (new, to_change))
