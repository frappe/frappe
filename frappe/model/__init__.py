# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# model __init__.py
from __future__ import unicode_literals
import frappe
import json


no_value_fields = ('Section Break', 'Column Break', 'HTML', 'Table', 'Button', 'Image',
	'Fold', 'Heading')
display_fieldtypes = ('Section Break', 'Column Break', 'HTML', 'Button', 'Image', 'Fold', 'Heading')
default_fields = ('doctype','name','owner','creation','modified','modified_by',
	'parent','parentfield','parenttype','idx','docstatus')
optional_fields = ("_user_tags", "_comments", "_assign", "_liked_by", "_seen")

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
