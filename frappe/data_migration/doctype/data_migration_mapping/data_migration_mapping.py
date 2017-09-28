# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DataMigrationMapping(Document):
	def get_filters(self):
		if self.condition:
			return frappe.safe_eval(self.condition, dict(frappe=frappe))

	def get_fields(self):
		fields = []
		for f in self.fields:
			if not (f.local_fieldname[0] in ('"', "'") or f.local_fieldname.startswith('eval:')):
				fields.append(f.local_fieldname)

		if frappe.db.has_column(self.local_doctype, self.migration_id_field):
			fields.append(self.migration_id_field)

		if 'name' not in fields:
			fields.append('name')

		return fields

	def get_mapped_record(self, doc):
		mapped = frappe._dict()

		key_fieldname = 'remote_fieldname'
		value_fieldname = 'local_fieldname'

		if self.mapping_type == 'Pull':
			key_fieldname, value_fieldname = value_fieldname, key_fieldname

		for field_map in self.fields:
			if not field_map.is_child_table:
				value = get_value_from_fieldname(field_map, value_fieldname, doc)
				mapped[field_map.get(key_fieldname)] = value
			else:
				mapping_name = field_map.child_table_mapping
				value = get_mapped_child_records(mapping_name, doc.get(field_map.get(value_fieldname)))
				mapped[field_map.get(key_fieldname)] = value
		return mapped

def get_mapped_child_records(mapping_name, child_docs):
	mapped_child_docs = []
	mapping = frappe.get_doc('Data Migration Mapping', mapping_name)
	for child_doc in child_docs:
		mapped_child_docs.append(mapping.get_mapped_record(child_doc))

	return mapped_child_docs

def get_value_from_fieldname(field_map, fieldname_field, doc):
	field_name = field_map.get(fieldname_field)

	if field_name.startswith('eval:'):
		value = frappe.safe_eval(field_name[5:], dict(frappe=frappe))
	elif field_name[0] in ('"', "'"):
		value = field_name[1:-1]
	else:
		value = doc.get(field_name)
	return value
