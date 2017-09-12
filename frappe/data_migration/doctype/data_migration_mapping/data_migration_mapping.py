# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document

class DataMigrationMapping(Document):

	def run_mapping(self, run, condition=None):
		connection = run.get_connection()
		start = run.current_mapping_start

		if self.mapping_type == 'Push':
			done = self.push(connection, start, condition)
		elif self.mapping_type == 'Pull':
			done = self.pull(connection, start, condition)

		if done:
			run.enqueue_next_mapping()
		else:
			run.enqueue_next_page(start = start + self.page_length)

	def push(self, connection, start, condition):
		data = self.get_data(start, condition)

		failed_items = []
		for d in data:
			migration_id_value = d.get(self.migration_id_field)
			response = connection.push(self.remote_objectname, self.get_mapped_record(d), migration_id_value)
			if response.ok:
				if not migration_id_value:
					frappe.db.set_value(self.local_doctype, d.name, self.migration_id_field, response.doc['name'], update_modified=False)
					frappe.db.commit()
			else:
				failed_items.append(response.doc)

		if len(data) < self.page_length:
			return frappe._dict(dict(
				done=True,
				failed_items=failed_items
			))

		return frappe._dict(dict(
			done=False,
			failed_items=failed_items
		))

	def get_data(self, start=0, condition=None, count=False):
		filters = {}
		if self.condition:
			filters = frappe.safe_eval(self.condition, dict(frappe=frappe))

		if condition:
			filters.update(condition)

		if count:
			return frappe.get_all(self.local_doctype, ['count(name) as total'], filters=filters)[0].total
		else:
			return frappe.get_all(self.local_doctype, fields=self.get_fields(), filters=filters, start=start,
				page_length=self.page_length, debug=True)

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
			else:
				value = d.get(f.local_fieldname)
			mapped[f.remote_fieldname] = value

		return mapped

	# def get_deleted_documents(self):
	# 	frappe.get_all('Deleted Document', dict(
	# 		deleted_doctype=self.local_doctype,
	# 		modified=('>', )
	# 	))

	def pull(self, connection, start, page_length):
		data = connection.get_objects(self.remote_objectname, self.condition, "*", start=start, page_length=page_length)
		# self.make_custom_fields(self.local_doctype) # Creating a custom field for primary key

		# pre process
		if self.pre_process:
			exec self.pre_process in locals()

		for i, self.source in enumerate(data):
			# Fetchnig the appropriate doctype
			target = self.fetch_doctype()
			target.set('migration_key', self.source.get('id')) # Setting migration key

			self.store_mapped_data(target) # fetching data and storing it appropriately
