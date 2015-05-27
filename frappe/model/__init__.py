# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# model __init__.py
from __future__ import unicode_literals
import frappe
import json


no_value_fields = ('Section Break', 'Column Break', 'HTML', 'Table', 'Button', 'Image', 'Fold', 'Heading')
display_fieldtypes = ('Section Break', 'Column Break', 'HTML', 'Button', 'Image', 'Fold', 'Heading')
default_fields = ('doctype','name','owner','creation','modified','modified_by',
	'parent','parentfield','parenttype','idx','docstatus')
integer_docfield_properties = ("reqd", "search_index", "in_list_view", "permlevel",
	"hidden", "read_only", "ignore_user_permissions", "allow_on_submit", "report_hide",
	"in_filter", "no_copy", "print_hide", "unique")
optional_fields = ("_user_tags", "_comments", "_assign", "_starred_by")

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

	meta = frappe.get_meta(doctype, cached=False)
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

		update_reports(doctype, old_fieldname, new_fieldname)
		update_users_report_view_settings(doctype, old_fieldname, new_fieldname)

	# update in property setter
	frappe.db.sql("""update `tabProperty Setter` set field_name = %s
		where doc_type=%s and field_name=%s""", (new_fieldname, doctype, old_fieldname))

def update_reports(doctype, old_fieldname, new_fieldname):
	def _get_new_sort_by(report_dict, report, key):
		sort_by = report_dict.get(key) or ""
		if sort_by:
			sort_by = sort_by.split(".")
			if len(sort_by) > 1:
				if sort_by[0]==doctype and sort_by[1]==old_fieldname:
					sort_by = doctype + "." + new_fieldname
					report_dict["updated"] = True
			elif report.ref_doctype == doctype and sort_by[0]==old_fieldname:
				sort_by = doctype + "." + new_fieldname
				report_dict["updated"] = True

			if isinstance(sort_by, list):
				sort_by = '.'.join(sort_by)

		return sort_by

	reports = frappe.db.sql("""select name, ref_doctype, json from tabReport
		where report_type = 'Report Builder' and ifnull(is_standard, 'No') = 'No'
		and json like %s and json like %s""",
		('%%%s%%' % old_fieldname , '%%%s%%' % doctype), as_dict=True)

	for r in reports:
		report_dict = json.loads(r.json)

		# update filters
		new_filters = []
		for f in report_dict.get("filters"):
			if f and len(f) > 1 and f[0] == doctype and f[1] == old_fieldname:
				new_filters.append([doctype, new_fieldname, f[2], f[3]])
				report_dict["updated"] = True
			else:
				new_filters.append(f)

		# update columns
		new_columns = []
		for c in report_dict.get("columns"):
			if c and len(c) > 1 and c[0] == old_fieldname and c[1] == doctype:
				new_columns.append([new_fieldname, doctype])
				report_dict["updated"] = True
			else:
				new_columns.append(c)

		# update sort by
		new_sort_by = _get_new_sort_by(report_dict, r, "sort_by")
		new_sort_by_next = _get_new_sort_by(report_dict, r, "sort_by_next")

		if report_dict.get("updated"):
			new_val = json.dumps({
				"filters": new_filters,
				"columns": new_columns,
				"sort_by": new_sort_by,
				"sort_order": report_dict.get("sort_order"),
				"sort_by_next": new_sort_by_next,
				"sort_order_next": report_dict.get("sort_order_next")
			})

			frappe.db.sql("""update `tabReport` set `json`=%s where name=%s""", (new_val, r.name))

def update_users_report_view_settings(doctype, ref_fieldname, new_fieldname):
	user_report_cols = frappe.db.sql("""select defkey, defvalue from `tabDefaultValue` where
		defkey like '_list_settings:%'""")
	for key, value in user_report_cols:
		new_columns = []
		columns_modified = False
		for field, field_doctype in json.loads(value):
			if field == ref_fieldname and field_doctype == doctype:
				new_columns.append([new_fieldname, field_doctype])
				columns_modified=True
			else:
				new_columns.append([field, field_doctype])

		if columns_modified:
			frappe.db.sql("""update `tabDefaultValue` set defvalue=%s
				where defkey=%s""" % ('%s', '%s'), (json.dumps(new_columns), key))
