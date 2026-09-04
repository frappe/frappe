# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
<<<<<<< HEAD
=======
from frappe.query_builder import functions
>>>>>>> 17826e9002 (refactor: Use get_query instead of raw query (#41366))


@frappe.whitelist()
def get_all_nodes(doctype: str, label: str, parent: str, tree_method: str | None, **filters):
	"""Recursively gets all data from tree nodes"""

	filters.pop("cmd", None)
	filters.pop("data", None)

	try:
		tree_method = frappe.override_whitelisted_method(tree_method)
		callable_tree_method = frappe.get_attr(tree_method)
	except Exception as e:
		frappe.throw(_("Failed to get method for command {0} with {1}").format(tree_method, str(e)))

	frappe.is_whitelisted(callable_tree_method)

	data = callable_tree_method(doctype, parent, **filters)
	out = [dict(parent=label, data=data)]

	filters.pop("is_root", None)
	to_check = [d.get("value") for d in data if d.get("expandable")]

	while to_check:
		parent = to_check.pop()
		data = callable_tree_method(doctype, parent, is_root=False, **filters)
		out.append(dict(parent=parent, data=data))
		for d in data:
			if d.get("expandable"):
				to_check.append(d.get("value"))

	return out


@frappe.whitelist()
def get_children(doctype: str, parent: str = "", **filters):
	return _get_children(doctype, parent)


def _get_children(doctype, parent="", ignore_permissions=False):
	meta = frappe.get_meta(doctype)
	table = frappe.qb.DocType(doctype)
	parent_field = meta.get("nsm_parent_field") or "parent_" + frappe.scrub(doctype)
	filters = [[f"ifnull(`{parent_field}`,'')", "=", parent], ["docstatus", "<", 2]]

<<<<<<< HEAD
	return frappe.get_list(
		doctype,
		fields=[
			"name as value",
			"{} as title".format(meta.get("title_field") or "name"),
			"is_group as expandable",
		],
		filters=filters,
		order_by="name",
		ignore_permissions=ignore_permissions,
	)
=======
	filters = [["docstatus", "<", 2]]
	if frappe.db.has_column(doctype, "disabled") and not include_disabled:
		# used 0 instead of `false` since type of check in postgres is smallint
		filters.append(["disabled", "=", 0])

	qb = frappe.qb.get_query(
		doctype,
		fields=[
			"name as value",
			f"{meta.get('title_field') or 'name'} as title",
			"is_group as expandable",
		],
		filters=filters,
		order_by="name asc",
		ignore_permissions=ignore_permissions,
	).where(functions.IfNull(table[parent_field], "").eq(parent))

	return qb.run(as_dict=True)
>>>>>>> 17826e9002 (refactor: Use get_query instead of raw query (#41366))


@frappe.whitelist()
def add_node():
	args = make_tree_args(**frappe.form_dict)
	doc = frappe.get_doc(args)

	doc.save()


def make_tree_args(**kwarg):
	kwarg.pop("cmd", None)

	doctype = kwarg["doctype"]
	parent_field = "parent_" + frappe.scrub(doctype)

	if kwarg["is_root"] == "false":
		kwarg["is_root"] = False
	if kwarg["is_root"] == "true":
		kwarg["is_root"] = True

	kwarg.update({parent_field: kwarg.get("parent") or kwarg.get(parent_field)})

	return frappe._dict(kwarg)
