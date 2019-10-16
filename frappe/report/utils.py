from __future__ import print_function
import frappe
import json
from six import string_types

def convert_string_to_column_def(col_string):
	full_split = col_string.split(':')
	label_def, fieldtype_def, width = full_split + ['' for i in range(3 - len(full_split))]

	label_def_split = label_def.split('/')
	label, fieldname = None, None
	if len(label_def_split) == 2:
		label, fieldname = label_def_split
	else:
		label = label_def_split[0]
		fieldname = frappe.scrub(label)

	fieldtype_def_split = fieldtype_def.split('/')
	fieldtype, options = None, None
	if len(fieldtype_def_split) == 2:
		fieldtype, options = fieldtype_def_split
	else:
		fieldtype = fieldtype_def_split[0] or 'Data'
		options = ''

	precision = 2
	try:
		try:
			width, precision = width.split('|')
		except ValueError:
			pass
		width = int(width)
		precision = int(precision)
	except ValueError:
		width = 150

	return {
		'fieldname': fieldname,
		'fieldtype': fieldtype,
		'label': label,
		'options': options,
		'width': width,
		'precision': precision,
	}

def get_column_def(columns, filters={'make_non_leaf_nodes': True}):
	columns = [
		convert_string_to_column_def(column_name)
		if isinstance(column_name, string_types)
		else column_name
		for column_name in columns
	]
	if not filters.get('make_non_leaf_nodes'):
		for column in columns:
			if column.get('fieldname') == 'warehouse':
				try:
					del column['is_tree']
				except KeyError:
					pass
				break
	return columns