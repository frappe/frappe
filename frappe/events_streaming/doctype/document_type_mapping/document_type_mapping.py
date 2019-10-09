# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class DocumentTypeMapping(Document):
	def get_mapped_doc(self, update):
		doc = frappe._dict(json.loads(update))
		for mapping in self.field_mapping:
			if doc.get(mapping.remote_fieldname):

				if mapping.is_child_table:
					doc[mapping.local_fieldname] = self.get_mapped_child_table_docs(mapping.child_table_mapping, doc[mapping.remote_fieldname])
					doc.pop(mapping.remote_fieldname, None)

				else:
					#copy value into local fieldname key and remove remote fieldname key
					doc[mapping.local_fieldname] = doc[mapping.remote_fieldname]
					doc.pop(mapping.remote_fieldname, None)

		doc['doctype'] = self.local_doctype
		return frappe.as_json(doc)

	def get_mapped_child_table_docs(self, child_map, table_entries):
		child_map = frappe.get_doc('Document Type Mapping', child_map)
		mapped_entries = []
		for entry in table_entries:
			child_doc = entry
			for mapping in child_map.field_mapping:
				if child_doc.get(mapping.remote_fieldname):
					child_doc[mapping.local_fieldname] = child_doc[mapping.remote_fieldname]
					child_doc.pop(mapping.remote_fieldname, None)
			child_doc['doctype'] = child_map.local_doctype
			mapped_entries.append(child_doc)
		return mapped_entries