# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

@frappe.whitelist()
def get_all_nodes(doctype, parent, tree_method, **filters):
	'''Recursively gets all data from tree nodes'''

	if 'cmd' in filters:
		del filters['cmd']

	filters.pop('data', None)

	tree_method = frappe.get_attr(tree_method)

	if not tree_method in frappe.whitelisted:
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	data = tree_method(doctype, parent, **filters)
	out = [dict(parent=parent, data=data)]

	if 'is_root' in filters:
		del filters['is_root']
	to_check = [d.get('value') for d in data if d.get('expandable')]

	while to_check:
		parent = to_check.pop()
		data = tree_method(doctype, parent, is_root=False, **filters)
		out.append(dict(parent=parent, data=data))
		for d in data:
			if d.get('expandable'):
				to_check.append(d.get('value'))

	return out

@frappe.whitelist()
def get_children(doctype, parent='', **filters):
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')
	filters=[['ifnull(`{0}`,"")'.format(parent_field), '=', parent],
		['docstatus', '<' ,'2']]

	doctype_meta = frappe.get_meta(doctype)
	data = frappe.get_list(doctype, fields=[
		'name as value',
		'{0} as title'.format(doctype_meta.get('title_field') or 'name'),
		'is_group as expandable'],
		filters=filters,
		order_by='name')

	return data

@frappe.whitelist()
def add_node():
	args = make_tree_args(**frappe.form_dict)
	doc = frappe.get_doc(args)

	doc.save()

def make_tree_args(**kwarg):
	del kwarg['cmd']

	doctype = kwarg['doctype']
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')
	name_field = kwarg.get('name_field', doctype.lower().replace(' ', '_') + '_name')

	if kwarg['is_root'] == 'false': kwarg['is_root'] = False
	if kwarg['is_root'] == 'true': kwarg['is_root'] = True

	kwarg.update({
		name_field: kwarg[name_field],
		parent_field: kwarg.get("parent") or kwarg.get(parent_field)
	})

	return frappe._dict(kwarg)
