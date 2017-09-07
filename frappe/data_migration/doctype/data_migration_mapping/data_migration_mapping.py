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
		filters = json.loads(self.condition or '{}')
		fields = [f.local_fieldname for f in self.fields]

		if frappe.db.has_column(self.local_doctype, 'migration_id'):
			fields.append('migration_id')

		data = frappe.get_all(self.local_doctype, fields=fields, filters=filters)

		for d in data:
			connection.push(self.remote_objectname, d, d.migration_id)

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