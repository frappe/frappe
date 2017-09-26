# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, base64, json
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

	def get_mapped_record(self, d):
		mapped = frappe._dict()

		key_fieldname = 'remote_fieldname'
		value_fieldname = 'local_fieldname'
		if self.mapping_type == 'Pull':
			key_fieldname, value_fieldname = value_fieldname, key_fieldname

		for f in self.fields:
			value = get_field_value(f, value_fieldname, d)
			if not f.get('is_child_table'):
				mapped[f.get(key_fieldname)] = value
			else:
				if mapped.get(f.get(key_fieldname)):
					mapped[f.get(key_fieldname)]['child_docs'].append()
				else:
					remote_child_docs = mapped[f.get(key_fieldname)]
					remote_child_docs = frappe._dict()
					remote_child_docs['doctype'] = []

		return mapped

def get_field_value(field_map, field_name, doc):
	current_val = field_map.get(field_name)
	if current_val.startswith('eval:'):
		value = frappe.safe_eval(current_val[5:], dict(frappe=frappe))
	elif current_val[0] in ('"', "'"):
		value = current_val[1:-1]
	elif field_map.formula and doc.get(current_val):
		exec field_map.formula in locals()
		value = modified_field_value
	else:
		value = doc.get(current_val)
	return value
