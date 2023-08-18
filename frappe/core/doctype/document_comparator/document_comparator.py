# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.core.doctype.version.version import get_diff
from frappe.model.document import Document


class DocumentComparator(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doctype_name: DF.Link | None
		document: DF.DynamicLink | None
	# end: auto-generated types
	pass

	@frappe.whitelist()
	def compare_document(self):
		amended_document_names = frappe.db.get_list(
			self.doctype_name,
			filters={"name": ("like", "%" + self.document + "%")},
			order_by="modified",
			pluck="name",
			limit=5,
		)
		amended_docs = [frappe.get_doc(self.doctype_name, name) for name in amended_document_names]

		changed = {}
		row_changed = {}
		for i in range(1, len(amended_docs)):
			diff = get_diff(amended_docs[i - 1], amended_docs[i], compare_cancelled=True)
			changed = get_diff_grid(amended_docs, i, diff, "changed", changed)
			row_changed = get_rows_updated_grid(amended_docs, i, diff, "row_changed", row_changed)

		return amended_document_names, {
			"changed": changed,
			"row_changed": row_changed,
		}


def get_diff_grid(amended_docs, i, diff, key, changed_fields):
	for change in diff[key]:
		fieldname = get_field_label(change[0], doctype=amended_docs[0].doctype)
		value = change[-1]
		if fieldname not in changed_fields:
			changed_fields[fieldname] = [""] * len(amended_docs)
		changed_fields[fieldname][i] = value if value else ""

		if i == 1:
			value = change[1]
			changed_fields[fieldname][i - 1] = value if value else ""

	return changed_fields


def get_rows_updated_grid(amended_docs, i, diff, key, changed_fields):
	for change in diff[key]:
		table_name = get_field_label(change[0], doctype=amended_docs[0].doctype)
		changed_fields[table_name] = {"index": change[1]}
		for field in change[-1]:
			fieldname = get_field_label(field[0], is_child=True)
			value = field[-1]
			if fieldname not in changed_fields[table_name]:
				changed_fields[table_name][fieldname] = [""] * len(amended_docs)
			changed_fields[table_name][fieldname][i] = value if value else ""

			if i == 1:
				value = field[1]
				changed_fields[table_name][fieldname][i - 1] = value if value else ""

	return changed_fields


def get_field_label(fieldname, doctype=None, is_child=False):
	if is_child:
		label = frappe.db.get_value("DocField", {"fieldname": fieldname}, "label")
		return label

	meta = frappe.get_meta(doctype)
	label = meta.get_label(fieldname)
	if label not in ["No Label", "None", ""]:
		return label
	return fieldname
