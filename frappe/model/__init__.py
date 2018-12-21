# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# model __init__.py
from __future__ import unicode_literals
import frappe
import json

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
default_fields = ('doctype','name','owner','creation','modified','modified_by',
	'parent','parentfield','parenttype','idx','docstatus')
optional_fields = ("_user_tags", "_comments", "_assign", "_liked_by", "_seen")
table_fields = ('Table', 'Table MultiSelect')

def delete_fields(args_dict, delete=0):
	"""
		Delete a field.
		* Deletes record from `tabDocField`
		* If not single doctype: Drops column from table
		* If single, deletes record from `tabSingles`
		args_dict = { dt: [field names] }
	"""
	import frappe.utils
	for dt in list(args_dict):
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
