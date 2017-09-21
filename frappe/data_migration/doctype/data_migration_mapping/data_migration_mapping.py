# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os, base64, json
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files

class DataMigrationMapping(Document):
	def on_update(self):
		if frappe.local.conf.get('developer_mode'):
			record_list =[['Data Migration Mapping', self.name]]

			export_to_files(record_list=record_list, record_module=self.module)

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
		for f in self.fields:
			value = get_field_value(f, 'local_fieldname', d)
			if not f.get('is_child_table'):
				mapped[f.remote_fieldname] = value
			else:
				if mapped.get(f.remote_fieldname):
					mapped[f.remote_fieldname]['child_docs'].append()
				else:
					remote_child_docs = mapped[f.remote_fieldname]
					remote_child_docs = frappe._dict()
					remote_child_docs['doctype'] = []

		return mapped

	def insert_mapped_record(self, doc):
		if self.pre_process:
			doc = process_doc(doc, self.pre_process)
		if not frappe.db.exists(self.local_doctype, {self.local_primary_key: doc[self.local_primary_key]}):
			d = frappe.new_doc(self.local_doctype)
			for f in self.fields:
				value = get_field_value(f, 'remote_fieldname', doc)
				d.set(f.local_fieldname, doc[f.remote_fieldname])
			d.save(ignore_permissions=True)
			if self.post_process:
				process_doc(d.as_dict(), self.post_process)

def get_field_value(field_map, field_name, doc):
	current_val = field_map.get(field_name)
	if current_val.startswith('eval:'):
		value = frappe.safe_eval(current_val[5:], dict(frappe=frappe))
	elif current_val[0] in ('"', "'"):
		value = current_val[1:-1]
	elif field_map.formula and doc.get(current_val):
		value = frappe.safe_eval(field_map.formula.format(doc.get(current_val)),
			dict(frappe=frappe))
	else:
		value = doc.get(current_val)
	return value

def process_doc(doc, process_str):
	for key in doc:
		if doc[key] is None:
			doc[key] = ''
	code = process_str.format(json.dumps(doc))
	return json.loads(frappe.safe_eval(code, dict(frappe=frappe)))