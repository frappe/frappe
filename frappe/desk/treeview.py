# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.query_builder import Field, functions


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

	# A tree method may return a `node_id` per node when `value` alone is not unique
	# (e.g. the same item appearing at several places in a BOM tree). Recursion is
	# keyed on that id so sibling branches don't collapse into one another.
	# `parent_node_id` is only forwarded when set, since most tree methods take a
	# fixed set of keyword arguments and would reject an unexpected one.
	parent_node_id = filters.pop("parent_node_id", None)

	def get_data(parent, node_id, **kwargs):
		if node_id:
			kwargs["parent_node_id"] = node_id
		return callable_tree_method(doctype, parent, **kwargs)

	data = get_data(parent, parent_node_id, **filters)
	out = [dict(parent=parent_node_id or label, data=data)]

	filters.pop("is_root", None)
	to_check = [(d.get("value"), d.get("node_id")) for d in data if d.get("expandable")]

	while to_check:
		parent, node_id = to_check.pop()
		data = get_data(parent, node_id, is_root=False, **filters)
		out.append(dict(parent=node_id or parent, data=data))
		for d in data:
			if d.get("expandable"):
				to_check.append((d.get("value"), d.get("node_id")))

	return out


@frappe.whitelist()
def get_children(doctype: str, parent: str = "", include_disabled: str | int | bool = False, **filters):
	if isinstance(include_disabled, str):
		include_disabled = frappe.sbool(include_disabled)
	return _get_children(doctype, parent, include_disabled=include_disabled)


def _get_children(doctype, parent="", ignore_permissions=False, include_disabled=False):
	meta = frappe.get_meta(doctype)
	parent_field = meta.get("nsm_parent_field") or "parent_" + frappe.scrub(doctype)

	qb = (
		frappe.qb.from_(doctype)
		.select(
			Field("name").as_("value"),
			Field(meta.get("title_field") or "name").as_("title"),
			Field("is_group").as_("expandable"),
		)
		.where(functions.IfNull(Field(parent_field), "").eq(parent))
		.where(Field("docstatus") < 2)
	)

	if frappe.db.has_column(doctype, "disabled") and not include_disabled:
		# used 0 instead of `false` since type of check in postgres is smallint
		qb = qb.where(Field("disabled").eq(0))
	# Order by name and execute
	return qb.orderby("name").run(as_dict=True)


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

	parent = kwarg.get("parent") or kwarg.get(parent_field)
	if doctype != parent:
		kwarg.update({parent_field: parent})

	return frappe._dict(kwarg)
