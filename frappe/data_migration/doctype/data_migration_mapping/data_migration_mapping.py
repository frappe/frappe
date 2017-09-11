# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

class DataMigrationMapping(Document):

	def run_mapping(self, run, condition=None):
		self.make_custom_fields()

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

		for d in data:
			response = connection.push(self.remote_objectname, self.get_mapped_record(d), d.migration_id)
			if not d.migration_id:
				frappe.db.set_value(self.local_doctype, d.name, 'migration_id', response['name'], update_modified=False)
				frappe.db.commit()

		if len(data) < self.page_length:
			return True

		return False

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

		if frappe.db.has_column(self.local_doctype, 'migration_id'):
			fields.append('migration_id')

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

	def make_custom_fields(self):
		""" Add custom field for primary key """
		field = frappe.db.get_value("Custom Field", {"dt": self.local_doctype, "fieldname": 'migration_id'})
		if not field:
			create_custom_field(self.local_doctype, {
				'label': 'Migration ID',
				'fieldname': 'migration_id',
				'fieldtype': 'Data',
				'read_only': 1,
				'unique': 1
			})