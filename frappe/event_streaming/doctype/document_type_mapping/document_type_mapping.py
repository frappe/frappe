# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.model.document import Document


class DocumentTypeMapping(Document):
	def validate(self):
		# if inner mapping exists, the remote doctype should be common in both mappings
		# Only then the exact remote dependency doc can be fetched
		for field_map in self.field_mapping:
			if field_map.mapping_type == 'Document':
				inner_mapped_doctype = frappe.db.get_value('Document Type Mapping', field_map.mapping, 'remote_doctype')
				if self.remote_doctype != inner_mapped_doctype:
					msg = _('Row #{0}: The Remote Document Type of mapping').format(field_map.idx)
					msg += " <b><a href='#Form/{0}/{1}'>{1}</a></b> ".format(self.doctype, field_map.mapping)
					msg += _('and the current mapping should be the same.')
					frappe.throw(msg, title='Remote Document Type Mismatch')

	def get_mapped_update(self, doc, producer_site):
		remote_fields = []
		# list of tuples (local_fieldname, dependent_doc)
		dependencies = []

		for mapping in self.field_mapping:
			if doc.get(mapping.remote_fieldname):
				if mapping.mapping_type == 'Document':
					dependency = self.get_mapped_dependency(mapping, producer_site, doc.get(mapping.remote_fieldname), mapping.remote_fieldname)
					dependencies.append((mapping.local_fieldname, dependency))

				if mapping.mapping_type == 'Child Table':
						doc[mapping.local_fieldname] = self.get_mapped_child_table_docs(mapping.child_table_mapping, doc[mapping.remote_fieldname])
				else:
					# copy value into local fieldname key and remove remote fieldname key
					doc[mapping.local_fieldname] = doc[mapping.remote_fieldname]
				remote_fields.append(mapping.remote_fieldname)

			if not doc.get(mapping.local_fieldname) and mapping.default_value:
				doc[mapping.local_fieldname] = mapping.default_value

		#remove the remote fieldnames
		for field in remote_fields:
			doc.pop(field, None)
		doc['doctype'] = self.local_doctype

		mapped_update = {'doc': frappe.as_json(doc)}
		if len(dependencies):
			mapped_update['dependencies'] = dependencies
		return mapped_update


	def get_mapped_dependency(self, mapping, producer_site, dependent_field_val, dependent_field):
		inner_mapping = frappe.get_doc('Document Type Mapping', mapping.mapping)
		filters = {}
		for pair in inner_mapping.field_mapping:
			if pair.remote_fieldname == dependent_field:
				filters[pair.remote_fieldname] = dependent_field_val
				break

		matching_docs = producer_site.get_doc(inner_mapping.remote_doctype, filters=filters)
		if len(matching_docs):
			remote_docname = matching_docs[0].get('name')
		remote_doc = producer_site.get_doc(inner_mapping.remote_doctype, remote_docname)
		doc = inner_mapping.get_mapped_update(remote_doc, producer_site).get('doc')
		return doc


def get_mapped_child_table_docs(child_map, table_entries):
	"""Get mapping for child doctypes"""
	child_map = frappe.get_doc('Document Type Mapping', child_map)
	mapped_entries = []
	for child_doc in table_entries:
		for mapping in child_map.field_mapping:
			if child_doc.get(mapping.remote_fieldname):
				child_doc[mapping.local_fieldname] = child_doc[mapping.remote_fieldname]
				child_doc.pop(mapping.remote_fieldname, None)
		child_doc['doctype'] = child_map.local_doctype
		mapped_entries.append(child_doc)
	return mapped_entries
