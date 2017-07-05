# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.naming import validate_name
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.utils.password import rename_password

@frappe.whitelist()
def rename_doc(doctype, old, new, force=False, merge=False, ignore_permissions=False, ignore_if_exists=False):
	"""
		Renames a doc(dt, old) to doc(dt, new) and
		updates all linked fields of type "Link"
	"""
	if not frappe.db.exists(doctype, old):
		return

	if ignore_if_exists and frappe.db.exists(doctype, new):
		return

	if old==new:
		frappe.msgprint(_('Please select a new name to rename'))
		return

	force = cint(force)
	merge = cint(merge)

	meta = frappe.get_meta(doctype)

	# call before_rename
	old_doc = frappe.get_doc(doctype, old)
	out = old_doc.run_method("before_rename", old, new, merge) or {}
	new = (out.get("new") or new) if isinstance(out, dict) else (out or new)

	if doctype != "DocType":
		new = validate_rename(doctype, new, meta, merge, force, ignore_permissions)

	if not merge:
		rename_parent_and_child(doctype, old, new, meta)

	# update link fields' values
	link_fields = get_link_fields(doctype)
	update_link_field_values(link_fields, old, new, doctype)

	rename_dynamic_links(doctype, old, new)

	if doctype=='DocType':
		rename_doctype(doctype, old, new, force)

	update_attachments(doctype, old, new)

	if merge:
		frappe.delete_doc(doctype, old)

	# call after_rename
	new_doc = frappe.get_doc(doctype, new)

	# copy any flags if required
	new_doc._local = getattr(old_doc, "_local", None)

	new_doc.run_method("after_rename", old, new, merge)

	rename_versions(doctype, old, new)

	if not merge:
		rename_password(doctype, old, new)

	# update user_permissions
	frappe.db.sql("""update tabDefaultValue set defvalue=%s where parenttype='User Permission'
		and defkey=%s and defvalue=%s""", (new, doctype, old))
	frappe.clear_cache()

	if merge:
		new_doc.add_comment('Edit', _("merged {0} into {1}").format(frappe.bold(old), frappe.bold(new)))
	else:
		new_doc.add_comment('Edit', _("renamed from {0} to {1}").format(frappe.bold(old), frappe.bold(new)))

	return new

def update_attachments(doctype, old, new):
	try:
		if old != "File Data" and doctype != "DocType":
			frappe.db.sql("""update `tabFile` set attached_to_name=%s
				where attached_to_name=%s and attached_to_doctype=%s""", (new, old, doctype))
	except Exception as e:
		if e.args[0]!=1054: # in patch?
			raise

def rename_versions(doctype, old, new):
	frappe.db.sql("""update tabVersion set docname=%s where ref_doctype=%s and docname=%s""",
		(new, doctype, old))

def rename_parent_and_child(doctype, old, new, meta):
	# rename the doc
	frappe.db.sql("update `tab%s` set name=%s where name=%s" % (frappe.db.escape(doctype), '%s', '%s'),
		(new, old))
	update_autoname_field(doctype, new, meta)
	update_child_docs(old, new, meta)

def update_autoname_field(doctype, new, meta):
	# update the value of the autoname field on rename of the docname
	if meta.get('autoname'):
		field = meta.get('autoname').split(':')
		if field and field[0] == "field":
			frappe.db.sql("update `tab%s` set %s=%s where name=%s" % (frappe.db.escape(doctype), field[1], '%s', '%s'),
				(new, new))

def validate_rename(doctype, new, meta, merge, force, ignore_permissions):
	# using for update so that it gets locked and someone else cannot edit it while this rename is going on!
	exists = frappe.db.sql("select name from `tab{doctype}` where name=%s for update".format(doctype=frappe.db.escape(doctype)), new)
	exists = exists[0][0] if exists else None

	if merge and not exists:
		frappe.msgprint(_("{0} {1} does not exist, select a new target to merge").format(doctype, new), raise_exception=1)

	if exists and exists != new:
		# for fixing case, accents
		exists = None

	if (not merge) and exists:
		frappe.msgprint(_("Another {0} with name {1} exists, select another name").format(doctype, new), raise_exception=1)

	if not (ignore_permissions or frappe.has_permission(doctype, "write")):
		frappe.msgprint(_("You need write permission to rename"), raise_exception=1)

	if not (force or ignore_permissions) and not meta.allow_rename:
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

def update_child_docs(old, new, meta):
	# update "parent"
	for df in meta.get_table_fields():
		frappe.db.sql("update `tab%s` set parent=%s where parent=%s" \
			% (frappe.db.escape(df.options), '%s', '%s'), (new, old))

def update_link_field_values(link_fields, old, new, doctype):
	for field in link_fields:
		if field['issingle']:
			try:
				single_doc = frappe.get_doc(field['parent'])
				if single_doc.get(field['fieldname'])==old:
					single_doc.set(field['fieldname'], new)
					# update single docs using ORM rather then query
					# as single docs also sometimes sets defaults!
					single_doc.flags.ignore_mandatory = True
					single_doc.save(ignore_permissions=True)
			except ImportError:
				# fails in patches where the doctype has been renamed
				# or no longer exists
				pass
		else:
			# because the table hasn't been renamed yet!
			parent = field['parent'] if field['parent']!=new else old

			frappe.db.sql("""\
				update `tab%s` set `%s`=%s
				where `%s`=%s""" \
				% (frappe.db.escape(parent), frappe.db.escape(field['fieldname']), '%s',
					frappe.db.escape(field['fieldname']), '%s'),
				(new, old))

def get_link_fields(doctype):
	# get link fields from tabDocField
	link_fields = frappe.db.sql("""\
		select parent, fieldname,
			(select issingle from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.options=%s and df.fieldtype='Link'""", (doctype,), as_dict=1)

	# get link fields from tabCustom Field
	custom_link_fields = frappe.db.sql("""\
		select dt as parent, fieldname,
			(select issingle from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.options=%s and df.fieldtype='Link'""", (doctype,), as_dict=1)

	# add custom link fields list to link fields list
	link_fields += custom_link_fields

	# remove fields whose options have been changed using property setter
	property_setter_link_fields = frappe.db.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select issingle from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.property_type='options' and
			ps.field_name is not null and
			ps.value=%s""", (doctype,), as_dict=1)

	link_fields += property_setter_link_fields

	return link_fields

def update_options_for_fieldtype(fieldtype, old, new):
	if frappe.conf.developer_mode:
		for name in frappe.db.sql_list("""select parent from
			tabDocField where options=%s""", old):
			doctype = frappe.get_doc("DocType", name)
			save = False
			for f in doctype.fields:
				if f.options == old:
					f.options = new
					save = True
			if save:
				doctype.save()
	else:
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
			(select issingle from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.parent != %s and df.fieldtype = 'Select' and
			df.options like "%%%%%s%%%%" """ \
		% ('%s', frappe.db.escape(old)), (new,), as_dict=1)

	# get link fields from tabCustom Field
	custom_select_fields = frappe.db.sql("""\
		select dt as parent, fieldname,
			(select issingle from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.dt != %s and df.fieldtype = 'Select' and
			df.options like "%%%%%s%%%%" """ \
		% ('%s', frappe.db.escape(old)), (new,), as_dict=1)

	# add custom link fields list to link fields list
	select_fields += custom_select_fields

	# remove fields whose options have been changed using property setter
	property_setter_select_fields = frappe.db.sql("""\
		select ps.doc_type as parent, ps.field_name as fieldname,
			(select issingle from tabDocType dt
			where dt.name = ps.doc_type) as issingle
		from `tabProperty Setter` ps
		where
			ps.doc_type != %s and
			ps.property_type='options' and
			ps.field_name is not null and
			ps.value like "%%%%%s%%%%" """ \
		% ('%s', frappe.db.escape(old)), (new,), as_dict=1)

	select_fields += property_setter_select_fields

	return select_fields

def update_select_field_values(old, new):
	frappe.db.sql("""\
		update `tabDocField` set options=replace(options, %s, %s)
		where
			parent != %s and fieldtype = 'Select' and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', frappe.db.escape(old), frappe.db.escape(old)), (old, new, new))

	frappe.db.sql("""\
		update `tabCustom Field` set options=replace(options, %s, %s)
		where
			dt != %s and fieldtype = 'Select' and
			(options like "%%%%\\n%s%%%%" or options like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', frappe.db.escape(old), frappe.db.escape(old)), (old, new, new))

	frappe.db.sql("""\
		update `tabProperty Setter` set value=replace(value, %s, %s)
		where
			doc_type != %s and field_name is not null and
			property='options' and
			(value like "%%%%\\n%s%%%%" or value like "%%%%%s\\n%%%%")""" % \
		('%s', '%s', '%s', frappe.db.escape(old), frappe.db.escape(old)), (old, new, new))

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

def rename_dynamic_links(doctype, old, new):
	for df in get_dynamic_link_map().get(doctype, []):
		# dynamic link in single, just one value to check
		if frappe.get_meta(df.parent).issingle:
			refdoc = frappe.db.get_singles_dict(df.parent)
			if refdoc.get(df.options)==doctype and refdoc.get(df.fieldname)==old:

				frappe.db.sql("""update tabSingles set value=%s where
					field=%s and value=%s and doctype=%s""", (new, df.fieldname, old, df.parent))
		else:
			# because the table hasn't been renamed yet!
			parent = df.parent if df.parent != new else old
			frappe.db.sql("""update `tab{parent}` set {fieldname}=%s
				where {options}=%s and {fieldname}=%s""".format(parent = parent,
					fieldname=df.fieldname, options=df.options), (new, doctype, old))

def bulk_rename(doctype, rows=None, via_console = False):
	"""Bulk rename documents

	:param doctype: DocType to be renamed
	:param rows: list of documents as `((oldname, newname), ..)`"""
	if not rows:
		frappe.throw(_("Please select a valid csv file with data"))

	if not via_console:
		max_rows = 500
		if len(rows) > max_rows:
			frappe.throw(_("Maximum {0} rows allowed").format(max_rows))

	rename_log = []
	for row in rows:
		# if row has some content
		if len(row) > 1 and row[0] and row[1]:
			try:
				if rename_doc(doctype, row[0], row[1]):
					msg = _("Successful: {0} to {1}").format(row[0], row[1])
					frappe.db.commit()
				else:
					msg = _("Ignored: {0} to {1}").format(row[0], row[1])
			except Exception as e:
				msg = _("** Failed: {0} to {1}: {2}").format(row[0], row[1], repr(e))
				frappe.db.rollback()

			if via_console:
				print(msg)
			else:
				rename_log.append(msg)

	if not via_console:
		return rename_log
