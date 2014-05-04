# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.utils import cstr
from frappe.model import default_fields

def get_mapped_doc(from_doctype, from_docname, table_maps, target_doc=None,
		postprocess=None, ignore_permissions=False):

	source_doc = frappe.get_doc(from_doctype, from_docname)

	if not ignore_permissions:
		if not source_doc.has_permission("read"):
			source_doc.raise_no_permission_to("read")

	# main
	if not target_doc:
		target_doc = frappe.new_doc(table_maps[from_doctype]["doctype"])
	elif isinstance(target_doc, basestring):
		target_doc = frappe.get_doc(json.loads(target_doc))

	if not target_doc.has_permission("create"):
		target_doc.raise_no_permission_to("create")

	map_doc(source_doc, target_doc, table_maps[source_doc.doctype])

	row_exists_for_parentfield = {}

	# children
	for df in source_doc.meta.get_table_fields():
		source_child_doctype = df.options
		table_map = table_maps.get(source_child_doctype)
		if table_map:
			for source_d in source_doc.get(df.fieldname):
				if "condition" in table_map:
					if not table_map["condition"](source_d):
						continue

				target_child_doctype = table_map["doctype"]
				target_parentfield = target_doc.get_parentfield_of_doctype(target_child_doctype)

				# does row exist for a parentfield?
				if df.fieldname not in row_exists_for_parentfield:
					row_exists_for_parentfield[target_parentfield] = (True
						if target_doc.get(target_parentfield) else False)

				if table_map.get("add_if_empty") and row_exists_for_parentfield.get(target_parentfield):
					continue

				if table_map.get("filter") and table_map.get("filter")(source_d):
					continue

				target_d = frappe.new_doc(target_child_doctype, target_doc, target_parentfield)
				map_doc(source_d, target_d, table_map, source_doc)
				target_d.idx = None
				target_doc.append(target_parentfield, target_d)

	if postprocess:
		postprocess(source_doc, target_doc)

	return target_doc

def map_doc(source_doc, target_doc, table_map, source_parent=None):
	no_copy_fields = set([d.fieldname for d in source_doc.meta.get("fields") if (d.no_copy==1 or d.fieldtype=="Table")]
		+ [d.fieldname for d in target_doc.meta.get("fields") if (d.no_copy==1 or d.fieldtype=="Table")]
		+ default_fields
		+ table_map.get("field_no_map", []))

	if table_map.get("validation"):
		for key, condition in table_map["validation"].items():
			if condition[0]=="=":
				if source_doc.get(key) != condition[1]:
					frappe.throw(_("Cannot map because following condition fails: ")
						+ key + "=" + cstr(condition[1]))

	# map same fields
	for df in target_doc.meta.get("fields"):
		if df.fieldname not in no_copy_fields:
			val = source_doc.get(df.fieldname)
			if val not in (None, ""):
				target_doc.set(df.fieldname, val)

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

	if "postprocess" in table_map:
		table_map["postprocess"](source_doc, target_doc, source_parent)
