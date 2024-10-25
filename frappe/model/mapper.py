# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe import _
from frappe.model import child_table_fields, default_fields, table_fields
from frappe.model.document import read_only_document
from frappe.utils import cstr


@frappe.whitelist()
def make_mapped_doc(method, source_name, selected_children=None, args=None):
	"""Return the mapped document calling the given mapper method.
	Set `selected_children` as flags for the `get_mapped_doc` method.

	Called from `open_mapped_doc` from create_new.js"""

	for hook in reversed(frappe.get_hooks("override_whitelisted_methods", {}).get(method, [])):
		# override using the last hook
		method = hook
		break

	method = frappe.get_attr(method)

	frappe.is_whitelisted(method)

	if selected_children:
		selected_children = json.loads(selected_children)

	if args:
		frappe.flags.args = frappe._dict(json.loads(args))

	frappe.flags.selected_children = selected_children or None

	with read_only_document("doc-mapper"):
		return method(source_name)


@frappe.whitelist()
def map_docs(method, source_names, target_doc, args=None):
	"""Return the mapped document calling the given mapper method with each of the given source docs on the target doc.

	:param args: Args as string to pass to the mapper method

	e.g. args: "{ 'supplier': 'XYZ' }"
	"""

	method = frappe.get_attr(method)
	frappe.is_whitelisted(method)

	for src in json.loads(source_names):
		_args = (src, target_doc, json.loads(args)) if args else (src, target_doc)
		with read_only_document("doc-mapper"):
			target_doc = method(*_args)
	return target_doc


def get_mapped_doc(
	from_doctype,
	from_docname,
	table_maps,
	target_doc=None,
	postprocess=None,
	ignore_permissions: bool = False,
	ignore_child_tables: bool = False,
	cached: bool = False,
):
	apply_strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")

	# main
	if not target_doc:
		target_doctype = table_maps[from_doctype]["doctype"]
		if table_maps[from_doctype].get("on_parent"):
			target_parent = table_maps[from_doctype].get("on_parent")
			if isinstance(target_parent, str):
				target_parent = frappe.get_doc(json.loads(target_parent))
			target_parentfield = target_parent.get_parentfield_of_doctype(target_doctype)
			target_doc = frappe.new_doc(
				target_doctype, parent_doc=target_parent, parentfield=target_parentfield
			)
			target_parent.append(target_parentfield, target_doc)
			ret_doc = target_parent
		else:
			target_doc = frappe.new_doc(target_doctype)
			ret_doc = target_doc
	elif isinstance(target_doc, str):
		target_doc = frappe.get_doc(json.loads(target_doc))
		ret_doc = target_doc
	else:
		ret_doc = target_doc

	if (
		not apply_strict_user_permissions
		and not ignore_permissions
		and not target_doc.has_permission("create")
	):
		target_doc.raise_no_permission_to("create")

	if cached:
		source_doc = frappe.get_cached_doc(from_doctype, from_docname)
	else:
		source_doc = frappe.get_doc(from_doctype, from_docname)

	if not ignore_permissions:
		if not source_doc.has_permission("read"):
			source_doc.raise_no_permission_to("read")

	ret_doc.run_method("before_mapping", source_doc, table_maps)

	with read_only_document("doc-mapper"):
		map_doc(source_doc, target_doc, table_maps[source_doc.doctype])

	row_exists_for_parentfield = {}

	# children
	if not ignore_child_tables:
		for df in source_doc.meta.get_table_fields():
			source_child_doctype = df.options
			table_map = table_maps.get(source_child_doctype)

			# if table_map isn't explicitly specified check if both source and target have the same fieldname and same table options and both of them don't have no_copy
			if not table_map:
				target_df = target_doc.meta.get_field(df.fieldname)
				if target_df:
					target_child_doctype = target_df.options
					if (
						target_df
						and target_child_doctype == source_child_doctype
						and not df.no_copy
						and not target_df.no_copy
					):
						table_map = {"doctype": target_child_doctype}

			if table_map:
				target_child_doctype = table_map["doctype"]
				target_parentfield = target_doc.get_parentfield_of_doctype(target_child_doctype)

				if table_map.get("reset_value"):
					setattr(target_doc, target_parentfield, [])

				for source_d in source_doc.get(df.fieldname):
					if "condition" in table_map:
						if not table_map["condition"](source_d):
							continue

					# if children are selected (checked from UI) for this table type,
					# and this record is not in the selected children, then continue
					if (
						frappe.flags.selected_children
						and (df.fieldname in frappe.flags.selected_children)
						and source_d.name not in frappe.flags.selected_children[df.fieldname]
					):
						continue

					# does row exist for a parentfield?
					if target_parentfield not in row_exists_for_parentfield:
						row_exists_for_parentfield[target_parentfield] = (
							True if target_doc.get(target_parentfield) else False
						)

					if table_map.get("ignore"):
						continue

					if table_map.get("add_if_empty") and row_exists_for_parentfield.get(target_parentfield):
						continue

					if table_map.get("filter") and table_map.get("filter")(source_d):
						continue

					with read_only_document("doc-mapper"):
						map_child_doc(source_d, target_doc, table_map, source_doc)

	if postprocess:
		with read_only_document("doc-mapper"):
			postprocess(source_doc, target_doc)

	ret_doc.run_method("after_mapping", source_doc)
	ret_doc.set_onload("load_after_mapping", True)

	if apply_strict_user_permissions and not ignore_permissions and not ret_doc.has_permission("create"):
		ret_doc.raise_no_permission_to("create")

	return ret_doc


def map_doc(source_doc, target_doc, table_map, source_parent=None) -> None:
	if table_map.get("validation"):
		for key, condition in table_map["validation"].items():
			if condition[0] == "=" and source_doc.get(key) != condition[1]:
				frappe.throw(
					_("Cannot map because following condition fails:") + f" {key}={cstr(condition[1])}"
				)

	map_fields(source_doc, target_doc, table_map, source_parent)

	if "postprocess" in table_map:
		table_map["postprocess"](source_doc, target_doc, source_parent)


def map_fields(source_doc, target_doc, table_map, source_parent) -> None:
	no_copy_fields = set(
		[
			d.fieldname
			for d in source_doc.meta.get("fields")
			if (d.no_copy == 1 or d.fieldtype in table_fields)
		]
		+ [d.fieldname for d in target_doc.meta.get("fields") if (d.fieldtype in table_fields)]
		+ list(default_fields)
		+ list(child_table_fields)
		+ list(table_map.get("field_no_map", []))
	)

	for df in target_doc.meta.get("fields"):
		if df.fieldname not in no_copy_fields:
			# map same fields
			val = source_doc.get(df.fieldname)
			if val not in (None, ""):
				target_doc.set(df.fieldname, val)

			elif df.fieldtype == "Link":
				if not target_doc.get(df.fieldname):
					# map link fields having options == source doctype
					if df.options == source_doc.doctype:
						target_doc.set(df.fieldname, source_doc.name)

					elif source_parent and df.options == source_parent.doctype:
						target_doc.set(df.fieldname, source_parent.name)

	# map other fields
	field_map = table_map.get("field_map")

	if field_map:
		if isinstance(field_map, dict):
			for source_key, target_key in field_map.items():
				val = source_doc.get(source_key)
				if val not in (None, ""):
					target_doc.set(target_key, val)
		else:
			for fmap in field_map:
				val = source_doc.get(fmap[0])
				if val not in (None, ""):
					target_doc.set(fmap[1], val)

	# map idx
	if source_doc.idx:
		target_doc.idx = source_doc.idx

	# add fetch
	for df in target_doc.meta.get("fields", {"fieldtype": "Link"}):
		if target_doc.get(df.fieldname):
			map_fetch_fields(target_doc, df, no_copy_fields)


def map_fetch_fields(target_doc, df, no_copy_fields) -> None:
	linked_doc = None

	# options should be like "link_fieldname.fieldname_in_liked_doc"
	for fetch_df in target_doc.meta.get("fields", {"fetch_from": f"^{df.fieldname}."}):
		if not (fetch_df.fieldtype == "Read Only" or fetch_df.read_only):
			continue

		if (
			not target_doc.get(fetch_df.fieldname) or fetch_df.fieldtype == "Read Only"
		) and fetch_df.fieldname not in no_copy_fields:
			source_fieldname = fetch_df.fetch_from.split(".")[1]

			if not linked_doc:
				try:
					linked_doc = frappe.get_doc(df.options, target_doc.get(df.fieldname))
				except Exception:
					return

			val = linked_doc.get(source_fieldname)

			if val not in (None, ""):
				target_doc.set(fetch_df.fieldname, val)


def map_child_doc(source_d, target_parent, table_map, source_parent=None):
	target_child_doctype = table_map["doctype"]
	target_parentfield = target_parent.get_parentfield_of_doctype(target_child_doctype)
	target_d = frappe.new_doc(target_child_doctype, parent_doc=target_parent, parentfield=target_parentfield)

	map_doc(source_d, target_d, table_map, source_parent)

	target_d.idx = None
	target_parent.append(target_parentfield, target_d)
	return target_d
