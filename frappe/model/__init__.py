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

no_value_fields = ('Section Break', 'Column Break', 'HTML', 'Table', 'Button', 'Image',
	'Fold', 'Heading')
display_fieldtypes = ('Section Break', 'Column Break', 'HTML', 'Button', 'Image', 'Fold', 'Heading')
default_fields = ('doctype','name','owner','creation','modified','modified_by',
	'parent','parentfield','parenttype','idx','docstatus')
optional_fields = ("_user_tags", "_comments", "_assign", "_liked_by", "_seen")