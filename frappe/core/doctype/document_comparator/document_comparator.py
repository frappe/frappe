# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.core.doctype.version.version import get_diff
from frappe.model.document import Document


class DocumentComparator(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doctype_name: DF.Link
		document: DF.DynamicLink
	# end: auto-generated types
	pass

	def validate(self):
		self.validate_doctype_name()
		self.validate_document()

	def validate_doctype_name(self):
		if not self.doctype_name:
			frappe.throw(_("{} field cannot be empty.").format(frappe.bold("Doctype")))

	def validate_document(self):
		if not self.document:
			frappe.throw(_("{} field cannot be empty.").format(frappe.bold("Document")))

	@frappe.whitelist()
	def compare_document(self):
		self.validate()
		amended_document_names = frappe.db.get_list(
			self.doctype_name,
			filters={"name": ("like", "%" + self.document + "%")},
			order_by="modified",
			pluck="name",
			limit=5,
		)
		amended_docs = [frappe.get_doc(self.doctype_name, name) for name in amended_document_names]
		self.docs_to_compare = len(amended_docs)

		self.changed = {}
		self.row_changed = {}

		for i in range(1, self.docs_to_compare):
			diff = get_diff(amended_docs[i - 1], amended_docs[i], compare_cancelled=True)
			self.get_diff_grid(i, diff)
			self.get_rows_updated_grid(i, diff)

		return amended_document_names, {"changed": self.changed, "row_changed": self.row_changed}

	def get_diff_grid(self, i, diff):
		for change in diff.changed:
			fieldname = get_field_label(change[0], doctype=self.doctype_name)
			value = change[-1]
			if fieldname not in self.changed:
				self.changed[fieldname] = [""] * self.docs_to_compare
			self.changed[fieldname][i] = value or ""

			if i == 1:
				value = change[1]
				self.changed[fieldname][i - 1] = value or ""

	def get_rows_updated_grid(self, i, diff):
		# set an empty dictionary for each table
		# so it does not get overwritten for every change in same table
		for table in diff.row_changed:
			table_name = get_field_label(table[0], doctype=self.doctype_name)
			self.row_changed[table_name] = {}

		for change in diff.row_changed:
			table_name = get_field_label(change[0], doctype=self.doctype_name)
			index = change[1]
			self.row_changed[table_name][index] = {}
			for field in change[-1]:
				fieldname = get_field_label(field[0], is_child=True)
				value = field[-1]
				if fieldname not in self.row_changed[table_name][index]:
					self.row_changed[table_name][index][fieldname] = [""] * self.docs_to_compare
				self.row_changed[table_name][index][fieldname][i] = value or ""

				if i == 1:
					value = field[1]
					self.row_changed[table_name][index][fieldname][i - 1] = value or ""


def get_field_label(fieldname, doctype=None, is_child=False):
	if is_child:
		label = frappe.db.get_value("DocField", {"fieldname": fieldname}, "label")
		return label

	meta = frappe.get_meta(doctype)
	label = meta.get_label(fieldname)
	if label not in ["No Label", "None", ""]:
		return label
	return fieldname
