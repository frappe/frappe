# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document

class DataMigrationMapping(Document):
	def run(self, connection):
		if self.mapping_type == 'Push':
			self.push(connection)
		elif self.mapping_type == 'Pull':
			self.pull(connection)

	def push(self, connection):
		filters = {}
		fields = []
		if self.condition:
			filters = frappe.safe_eval(self.condition, dict(frappe=frappe))

		for f in self.fields:
			if not (f.local_fieldname[0] in ('"', "'") or f.local_fieldname.startswith('eval:')):
				fields.append(f.local_fieldname)

		if frappe.db.has_column(self.local_doctype, 'migration_id'):
			fields.append('migration_id')

		data = frappe.get_all(self.local_doctype, fields=fields, filters=filters)

		for d in data:
			mapped = frappe._dict()
			for f in self.fields:
				if f.local_fieldname.startswith('eval:'):
					value = frappe.safe_eval(f.local_fieldname[5:], dict(frappe=frappe))
				elif f.local_fieldname[0] in ('"', "'"):
					value = f.local_fieldname[1:-1]
				else:
					value = d.get(f.local_fieldname)
				mapped[f.remote_fieldname] = value
			connection.push(self.remote_objectname, mapped, d.migration_id)

	def pull(self, connection):
		data = connection.get_objects(self.remote_objectname, self.condition, "*")
		self.make_custom_fields(self.local_doctype) # Creating a custom field for primary key

		# pre process
		if self.pre_process:
			exec self.pre_process in locals()

		for i, self.source in enumerate(data):
			# Fetchnig the appropriate doctype
			target = self.fetch_doctype()
			target.set('migration_key', self.source.get('id')) # Setting migration key

			self.store_mapped_data(target) # fetching data and storing it appropriately