# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os, base64
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
		for f in self.fields:
			if f.local_fieldname.startswith('eval:'):
				value = frappe.safe_eval(f.local_fieldname[5:], dict(frappe=frappe))
			elif f.local_fieldname[0] in ('"', "'"):
				value = f.local_fieldname[1:-1]
			elif f.formula and d.get(f.local_fieldname):
				value = frappe.safe_eval(f.formula.format(d.get(f.local_fieldname)),
					dict(frappe=frappe));
			else:
				value = d.get(f.local_fieldname)

			if not f.is_child_table:
				mapped[f.remote_fieldname] = value
			else:
				if mapped.get(f.remote_fieldname):
					mapped[f.remote_fieldname]['child_docs'].append()
				else:
					remote_child_docs = mapped[f.remote_fieldname]
					remote_child_docs = frappe._dict()
					remote_child_docs['doctype'] = []

		return mapped
