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

	tree_method = frappe.get_attr(tree_method)

	if not tree_method in frappe.whitelisted:
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	data = tree_method(doctype, parent, **filters)
	out = [dict(parent=parent, data=data)]

	if 'is_root' in filters:
		del filters['is_root']

	to_check = [d.value for d in data if d.expandable]

	while to_check:
		parent = to_check.pop()
		data = tree_method(doctype, parent, is_root = False, **filters)
		out.append(dict(parent=parent, data=data))
		for d in data:
			if d.expandable:
				to_check.append(d.value)

	return out

@frappe.whitelist()
def get_children(doctype, parent='', **filters):
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')

	return frappe.db.sql("""select name as value, `{title_field}` as title,
		is_group as expandable
		from `tab{ctype}`
		where docstatus < 2
		and ifnull(`{parent_field}`,'') = %s
		order by name""".format(
			ctype = frappe.db.escape(doctype),
			parent_field = frappe.db.escape(parent_field),
			title_field = frappe.get_meta(doctype).title_field or 'name'),
		parent, as_dict=1)

@frappe.whitelist()
def add_node():
	args = make_tree_args(**frappe.form_dict)
	doc = frappe.get_doc(args)

	if args.doctype == "Sales Person":
		doc.employee = frappe.form_dict.get('employee')

	doc.save()

def make_tree_args(**kwarg):
	del kwarg['cmd']

	doctype = kwarg['doctype']
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')
	name_field = kwarg.get('name_field', doctype.lower().replace(' ', '_') + '_name')

	kwarg.update({
		name_field: kwarg[name_field],
		parent_field: kwarg.get("parent") or kwarg.get(parent_field)
	})

	return frappe._dict(kwarg)
