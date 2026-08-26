# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.query_builder import functions


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
def get_children(doctype: str, parent: str = "", include_disabled: str | int | bool = False, **filters):
	if isinstance(include_disabled, str):
		include_disabled = frappe.sbool(include_disabled)
	return _get_children(doctype, parent, include_disabled=include_disabled)


def _get_children(doctype, parent="", ignore_permissions=False, include_disabled=False):
	meta = frappe.get_meta(doctype)
	table = frappe.qb.DocType(doctype)
	parent_field = meta.get("nsm_parent_field") or "parent_" + frappe.scrub(doctype)

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


# guards against a corrupted parent chain sending the ancestor walk into a long loop
MAX_ANCESTOR_DEPTH = 100


def get_parent_field(doctype: str) -> str:
	"""Return the link field a node uses to point at its parent."""
	meta = frappe.get_meta(doctype)
	parent_field = meta.get("nsm_parent_field") or "parent_" + frappe.scrub(doctype)

	if not meta.has_field(parent_field):
		frappe.throw(
			_("{0} has no parent field, so it cannot be arranged as a tree.").format(_(doctype)),
			title=_("Not a Tree DocType"),
		)

	return parent_field


def is_descendant(doctype: str, ancestor: str, candidate: str, parent_field: str) -> bool:
	"""Whether `candidate` sits somewhere below `ancestor` in the tree.

	Walks up from the candidate rather than reading lft/rgt, so it also holds
	for tree DocTypes that are not nested sets.
	"""
	seen = set()
	current = candidate

	for _i in range(MAX_ANCESTOR_DEPTH):
		if not current or current in seen:
			return False
		if current == ancestor:
			return True
		seen.add(current)
		current = frappe.db.get_value(doctype, current, parent_field)

	return False


def validate_move(doctype: str, name: str, new_parent: str, parent_field: str) -> None:
	if new_parent == name:
		frappe.throw(_("{0} cannot be its own parent.").format(name))

	meta = frappe.get_meta(doctype)
	fields = ["name", "is_group"] if meta.has_field("is_group") else ["name"]
	target = frappe.db.get_value(doctype, new_parent, fields, as_dict=True)

	if not target:
		frappe.throw(
			_("{0} {1} does not exist.").format(_(doctype), new_parent),
			frappe.DoesNotExistError,
		)

	if meta.has_field("is_group") and not target.is_group:
		frappe.throw(_("{0} is not a group, so it cannot have children.").format(new_parent))

	if is_descendant(doctype, name, new_parent, parent_field):
		frappe.throw(_("Cannot move {0} into {1}, which is below it.").format(name, new_parent))


def apply_move(doctype: str, name: str, new_parent: str, parent_field: str) -> bool:
	"""Re-parent one node. Returns False when it already had that parent.

	Saves through the document, so the DocType's own validations, permission
	checks and nested set updates all still run.
	"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	if (doc.get(parent_field) or "") == new_parent:
		return False

	if new_parent:
		validate_move(doctype, name, new_parent, parent_field)

	doc.set(parent_field, new_parent or None)
	doc.save()
	return True


@frappe.whitelist(methods=["POST"])
def move_node(doctype: str, name: str, new_parent: str | None = None):
	"""Give one tree node a new parent.

	The parent fieldname is derived here rather than taken from the request,
	so this cannot be used to write arbitrary fields.
	"""
	if not doctype or not name:
		frappe.throw(_("DocType and name are required."))

	parent_field = get_parent_field(doctype)
	new_parent = (new_parent or "").strip()
	old_parent = frappe.db.get_value(doctype, name, parent_field) or ""

	moved = apply_move(doctype, name, new_parent, parent_field)

	return {"name": name, "parent": new_parent, "old_parent": old_parent, "moved": moved}


@frappe.whitelist(methods=["POST"])
def move_nodes(doctype: str, moves):
	"""Apply a whole editing session's worth of moves as one unit.

	Either all of them land or none do, so a move the tree cannot accept never
	leaves the hierarchy half rearranged. The request is already wrapped in a
	transaction, so throwing rolls the earlier saves back.
	"""
	if isinstance(moves, str):
		moves = json.loads(moves)

	if not moves:
		return {"moved": 0, "names": []}

	parent_field = get_parent_field(doctype)
	applied = []

	for move in moves:
		name = (move.get("name") or "").strip()
		new_parent = (move.get("parent") or "").strip()
		if not name:
			continue

		try:
			if apply_move(doctype, name, new_parent, parent_field):
				applied.append(name)
		except Exception as e:
			frappe.throw(
				_("{0} could not be moved: {1}").format(frappe.bold(name), str(e)),
				title=_("Nothing was saved"),
			)

	return {"moved": len(applied), "names": applied}
