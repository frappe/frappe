# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.core.doctype.version.version import get_diff
from frappe.model.document import Document
from frappe.utils import compare


class AuditTrail(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doctype_name: DF.Link
		document: DF.DynamicLink
		end_date: DF.Date | None
		start_date: DF.Date | None
	# end: auto-generated types

	pass

	def validate(self):
		self.validate_fields()
		self.validate_document()

	def validate_fields(self):
		fields_dict = {
			"DocType": self.doctype_name,
			"Document": self.document,
		}
		for field in fields_dict:
			if not fields_dict[field]:
				frappe.throw(_("{} field cannot be empty.").format(frappe.bold(field)))

	def validate_document(self):
		if not frappe.db.exists(self.doctype_name, self.document):
			frappe.throw(
				_("The selected document {0} is not a {1}.").format(
					frappe.bold(self.document), frappe.bold(self.doctype_name)
				)
			)

	@frappe.whitelist()
	def compare_document(self):
		self.validate()
		amended_document_names = self.get_amended_documents()
		self.amended_docs = [frappe.get_doc(self.doctype_name, name) for name in amended_document_names]
		self.docs_to_compare = len(self.amended_docs)
		self.changed, self.row_changed, self.added, self.removed = {}, {}, {}, {}

		for i in range(1, self.docs_to_compare):
			diff = get_diff(self.amended_docs[i - 1], self.amended_docs[i], compare_cancelled=True)
			self.get_diff_grid(i, diff)
			self.get_rows_added_removed_grid(i, diff, "added", self.added)
			self.get_rows_added_removed_grid(i, diff, "removed", self.removed)
			self.get_rows_updated_grid(i, diff)

		return amended_document_names, {
			"changed": self.changed,
			"row_changed": self.row_changed,
			"added": self.added,
			"removed": self.removed,
		}

	def get_amended_documents(self):
		start_date = self.get("start_date")
		amended_document_names = []
		curr_doc = self.document
		creation = frappe.db.get_value(self.doctype_name, self.document, "creation")
		while (
			curr_doc
			and len(amended_document_names) < 5
			and (start_date is None or compare(creation, ">=", start_date, "Date"))
		):
			amended_document_names.append(curr_doc)
			curr_doc = frappe.db.get_value(self.doctype_name, curr_doc, "amended_from")
			creation = frappe.db.get_value(self.doctype_name, curr_doc, "creation")
		amended_document_names = amended_document_names[::-1]

		return amended_document_names

	def get_diff_grid(self, i, diff):
		for change in diff.changed:
			fieldname = get_field_label(change[0], doctype=self.doctype_name)
			value = change[-1]
			value_list = [""] * self.docs_to_compare
			self.changed.setdefault(fieldname, value_list)
			self.changed[fieldname][i] = value or ""

			if i == 1:
				value = change[1]
				self.changed[fieldname][i - 1] = value or ""

	def get_rows_added_removed_grid(self, i, diff, key, changed_dict):
		doc_name = self.amended_docs[i].name
		changed_dict[doc_name] = {}
		for change in diff[key]:
			tablename = get_field_label(change[0], doctype=self.doctype_name)
			value_dict = filter_fields_for_gridview(change[-1])
			changed_dict[doc_name].setdefault(tablename, []).append(value_dict)

	def get_rows_updated_grid(self, i, diff):
		for change in diff.row_changed:
			table_name = get_field_label(change[0], doctype=self.doctype_name)
			index = change[1]
			self.row_changed.setdefault(table_name, {}).setdefault(index, {})
			for field in change[-1]:
				fieldname = get_field_label(field[0], doctype=self.doctype_name, child_field=change[0])
				value = field[-1]
				value_list = [""] * self.docs_to_compare
				self.row_changed[table_name][index].setdefault(fieldname, value_list)
				self.row_changed[table_name][index][fieldname][i] = value or ""

				if i == 1:
					value = field[1]
					self.row_changed[table_name][index][fieldname][i - 1] = value or ""


def get_field_label(fieldname, doctype, child_field=None):
	if child_field:
		meta = frappe.get_meta(doctype)
		for field in meta.fields:
			if field.fieldname == child_field:
				doctype = field.options

	meta = frappe.get_meta(doctype)
	label = meta.get_label(fieldname)
	if label not in ["No Label", None, ""]:
		return label
	return fieldname


def filter_fields_for_gridview(row):
	grid_row = {}
	meta = frappe.get_meta(row.doctype)
	for field in meta.fields:
		if field.in_list_view == 1:
			fieldlabel = get_field_label(field.fieldname, row.doctype)
			grid_row[fieldlabel] = row[field.fieldname] or ""

	return grid_row
