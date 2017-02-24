# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _

@frappe.whitelist()
def get_all_nodes(tree_method, tree_args, parent):
	'''Recursively gets all data from tree nodes'''

	tree_method = frappe.get_attr(tree_method)

	if not tree_method in frappe.whitelisted:
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	frappe.local.form_dict = frappe._dict(json.loads(tree_args))
	frappe.local.form_dict.parent = parent
	data = tree_method()
	out = [dict(parent=parent, data=data)]

	to_check = [d.value for d in data if d.expandable]
	while to_check:
		frappe.local.form_dict.parent = to_check.pop()
		data = tree_method()
		out.append(dict(parent=frappe.local.form_dict.parent, data=data))
		for d in data:
			if d.expandable:
				to_check.append(d.value)

	return out

@frappe.whitelist()
def get_children():
	doctype = frappe.local.form_dict.get('doctype')
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')
	parent = frappe.form_dict.get("parent") or ""

	return frappe.db.sql("""select name as value,
		is_group as expandable
		from `tab{ctype}`
		where docstatus < 2
		and ifnull(`{parent_field}`,'') = %s
		order by name""".format(ctype=frappe.db.escape(doctype), parent_field=frappe.db.escape(parent_field)),
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
	name_field = doctype.lower().replace(' ', '_') + '_name'
	
	kwarg.update({
		name_field: kwarg[name_field],
		parent_field: kwarg.get("parent") or kwarg.get(parent_field)
	})
	
	return frappe._dict(kwarg)
