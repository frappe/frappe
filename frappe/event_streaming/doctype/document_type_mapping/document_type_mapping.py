# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

from six import iteritems

import frappe
from frappe import _
from frappe.model import default_fields
from frappe.model.document import Document


class DocumentTypeMapping(Document):
	def validate(self):
		self.validate_inner_mapping()

	def validate_inner_mapping(self):
		meta = frappe.get_meta(self.local_doctype)
		for field_map in self.field_mapping:
			if field_map.local_fieldname not in default_fields:
				field = meta.get_field(field_map.local_fieldname)
				if not field:
					frappe.throw(_("Row #{0}: Invalid Local Fieldname").format(field_map.idx))

			fieldtype = field.get("fieldtype")
			if fieldtype in ["Link", "Dynamic Link", "Table"]:
				if not field_map.mapping and not field_map.default_value:
					msg = _(
						"Row #{0}: Please set Mapping or Default Value for the field {1} since its a dependency field"
					).format(field_map.idx, frappe.bold(field_map.local_fieldname))
					frappe.throw(msg, title="Inner Mapping Missing")

			if field_map.mapping_type == "Document" and not field_map.remote_value_filters:
				msg = _(
					"Row #{0}: Please set remote value filters for the field {1} to fetch the unique remote dependency document"
				).format(field_map.idx, frappe.bold(field_map.remote_fieldname))
				frappe.throw(msg, title="Remote Value Filters Missing")

	def get_mapping(self, doc, producer_site, update_type):
		remote_fields = []
		# list of tuples (local_fieldname, dependent_doc)
		dependencies = []

		for mapping in self.field_mapping:
			if doc.get(mapping.remote_fieldname):
				if mapping.mapping_type == "Document":
					if not mapping.default_value:
						dependency = self.get_mapped_dependency(mapping, producer_site, doc)
						if dependency:
							dependencies.append((mapping.local_fieldname, dependency))
					else:
						doc[mapping.local_fieldname] = mapping.default_value

				if mapping.mapping_type == "Child Table" and update_type != "Update":
					doc[mapping.local_fieldname] = get_mapped_child_table_docs(
						mapping.mapping, doc[mapping.remote_fieldname], producer_site
					)
				else:
					# copy value into local fieldname key and remove remote fieldname key
					doc[mapping.local_fieldname] = doc[mapping.remote_fieldname]

				if mapping.local_fieldname != mapping.remote_fieldname:
					remote_fields.append(mapping.remote_fieldname)

			if not doc.get(mapping.remote_fieldname) and mapping.default_value and update_type != "Update":
				doc[mapping.local_fieldname] = mapping.default_value

		# remove the remote fieldnames
		for field in remote_fields:
			doc.pop(field, None)

		if update_type != "Update":
			doc["doctype"] = self.local_doctype

		mapping = {"doc": frappe.as_json(doc)}
		if len(dependencies):
			mapping["dependencies"] = dependencies
		return mapping

	def get_mapped_update(self, update, producer_site):
		update_diff = frappe._dict(json.loads(update.data))
		mapping = update_diff
		dependencies = []
		if update_diff.changed:
			doc_map = self.get_mapping(update_diff.changed, producer_site, "Update")
			mapped_doc = doc_map.get("doc")
			mapping.changed = json.loads(mapped_doc)
			if doc_map.get("dependencies"):
				dependencies += doc_map.get("dependencies")

		if update_diff.removed:
			mapping = self.map_rows_removed(update_diff, mapping)
		if update_diff.added:
			mapping = self.map_rows(update_diff, mapping, producer_site, operation="added")
		if update_diff.row_changed:
			mapping = self.map_rows(update_diff, mapping, producer_site, operation="row_changed")

		update = {"doc": frappe.as_json(mapping)}
		if len(dependencies):
			update["dependencies"] = dependencies
		return update

	def get_mapped_dependency(self, mapping, producer_site, doc):
		inner_mapping = frappe.get_doc("Document Type Mapping", mapping.mapping)
		filters = json.loads(mapping.remote_value_filters)
		for key, value in iteritems(filters):
			if value.startswith("eval:"):
				val = frappe.safe_eval(value[5:], None, dict(doc=doc))
				filters[key] = val
			if doc.get(value):
				filters[key] = doc.get(value)
		matching_docs = producer_site.get_doc(inner_mapping.remote_doctype, filters=filters)
		if len(matching_docs):
			remote_docname = matching_docs[0].get("name")
			remote_doc = producer_site.get_doc(inner_mapping.remote_doctype, remote_docname)
			doc = inner_mapping.get_mapping(remote_doc, producer_site, "Insert").get("doc")
			return doc
		return

	def map_rows_removed(self, update_diff, mapping):
		removed = []
		mapping["removed"] = update_diff.removed
		for key, value in iteritems(update_diff.removed.copy()):
			local_table_name = frappe.db.get_value(
				"Document Type Field Mapping",
				{"remote_fieldname": key, "parent": self.name},
				"local_fieldname",
			)
			mapping.removed[local_table_name] = value
			if local_table_name != key:
				removed.append(key)

		# remove the remote fieldnames
		for field in removed:
			mapping.removed.pop(field, None)
		return mapping

	def map_rows(self, update_diff, mapping, producer_site, operation):
		remote_fields = []
		for tablename, entries in iteritems(update_diff.get(operation).copy()):
			local_table_name = frappe.db.get_value(
				"Document Type Field Mapping", {"remote_fieldname": tablename}, "local_fieldname"
			)
			table_map = frappe.db.get_value(
				"Document Type Field Mapping",
				{"local_fieldname": local_table_name, "parent": self.name},
				"mapping",
			)
			table_map = frappe.get_doc("Document Type Mapping", table_map)
			docs = []
			for entry in entries:
				mapped_doc = table_map.get_mapping(entry, producer_site, "Update").get("doc")
				docs.append(json.loads(mapped_doc))
			mapping.get(operation)[local_table_name] = docs
			if local_table_name != tablename:
				remote_fields.append(tablename)

		# remove the remote fieldnames
		for field in remote_fields:
			mapping.get(operation).pop(field, None)

		return mapping


def get_mapped_child_table_docs(child_map, table_entries, producer_site):
	"""Get mapping for child doctypes"""
	child_map = frappe.get_doc("Document Type Mapping", child_map)
	mapped_entries = []
	remote_fields = []
	for child_doc in table_entries:
		for mapping in child_map.field_mapping:
			if child_doc.get(mapping.remote_fieldname):
				child_doc[mapping.local_fieldname] = child_doc[mapping.remote_fieldname]
				if mapping.local_fieldname != mapping.remote_fieldname:
					child_doc.pop(mapping.remote_fieldname, None)
		mapped_entries.append(child_doc)

	# remove the remote fieldnames
	for field in remote_fields:
		child_doc.pop(field, None)

	child_doc["doctype"] = child_map.local_doctype
	return mapped_entries
