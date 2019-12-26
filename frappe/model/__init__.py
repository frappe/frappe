# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# model __init__.py
from __future__ import unicode_literals
import frappe

data_fieldtypes = (
	'Currency',
	'Int',
	'Long Int',
	'Float',
	'Percent',
	'Check',
	'Small Text',
	'Long Text',
	'Code',
	'Text Editor',
	'Markdown Editor',
	'HTML Editor',
	'Date',
	'Datetime',
	'Time',
	'Text',
	'Data',
	'Link',
	'Dynamic Link',
	'Password',
	'Select',
	'Rating',
	'Read Only',
	'Attach',
	'Attach Image',
	'Signature',
	'Color',
	'Barcode',
	'Geolocation'
)

no_value_fields = ('Section Break', 'Column Break', 'HTML', 'Table', 'Table MultiSelect', 'Button', 'Image',
	'Fold', 'Heading')
display_fieldtypes = ('Section Break', 'Column Break', 'HTML', 'Button', 'Image', 'Fold', 'Heading')
numeric_fieldtypes = ('Currency', 'Int', 'Long Int', 'Float', 'Percent', 'Check')
default_fields = ('doctype','name','owner','creation','modified','modified_by',
	'parent','parentfield','parenttype','idx','docstatus')
optional_fields = ("_user_tags", "_comments", "_assign", "_liked_by", "_seen")
table_fields = ('Table', 'Table MultiSelect')
core_doctypes_list = ('DocType', 'DocField', 'DocPerm', 'User', 'Role', 'Has Role',
	'Page', 'Module Def', 'Print Format', 'Report', 'Customize Form',
	'Customize Form Field', 'Property Setter', 'Custom Field', 'Custom Script')

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
	for dt in args_dict:
		fields = args_dict[dt]
		if not fields:
			continue

		frappe.db.sql("""
			DELETE FROM `tabDocField`
			WHERE parent='%s' AND fieldname IN (%s)
		""" % (dt, ", ".join(["'{}'".format(f) for f in fields])))

		# Delete the data/column only if delete is specified
		if not delete:
			continue

		if frappe.db.get_value("DocType", dt, "issingle"):
			frappe.db.sql("""
				DELETE FROM `tabSingles`
				WHERE doctype='%s' AND field IN (%s)
			""" % (dt, ", ".join(["'{}'".format(f) for f in fields])))
		else:
			existing_fields = frappe.db.multisql({
					"mariadb": "DESC `tab%s`" % dt,
					"postgres": """
						SELECT
 							COLUMN_NAME
						FROM
 							information_schema.COLUMNS
						WHERE
 							TABLE_NAME = 'tab%s';
					""" % dt,
				})
			existing_fields = existing_fields and [e[0] for e in existing_fields] or []
			fields_need_to_delete = set(fields) & set(existing_fields)
			if not fields_need_to_delete:
				continue

			if frappe.db.db_type == 'mariadb':
				# mariadb implicitly commits before DDL, make it explicit
				frappe.db.commit()

			query = "ALTER TABLE `tab%s` " % dt + \
				", ".join(["DROP COLUMN `%s`" % f for f in fields_need_to_delete])
			frappe.db.sql(query)

		if frappe.db.db_type == 'postgres':
			# commit the results to db
			frappe.db.commit()
