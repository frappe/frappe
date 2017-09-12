# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe import _

class DataMigrationRun(Document):

	def validate(self):
		exists = frappe.db.exists('Data Migration Run', dict(
			status=('in', ['Fail', 'Error'])
		))
		if exists:
			frappe.throw(_('There are failed runs with the same Data Migration Plan'))

	def run(self):
		self.begin()
		self.enqueue_next_mapping()

	def enqueue_next_mapping(self):
		next_mapping_name, percent_mappings_complete = self.get_next_mapping_and_percent_mappings_complete()
		if next_mapping_name:
			next_mapping = self.get_mapping(next_mapping_name)
			self.db_set(dict(
				current_mapping = next_mapping.name,
				current_mapping_start = 0,
				current_mapping_delete_start = 0,
				current_mapping_action = 'Insert'
			), notify=True, commit=True)
			frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping')
		else:
			self.complete()

	def enqueue_next_page(self):
		mapping = self.get_mapping(self.current_mapping)
		fields = dict(
			percent_complete = self.percent_complete + (100.0 / self.total_pages)
		)
		if self.current_mapping_action == 'Insert':
			start = self.current_mapping_start + mapping.page_length
			fields['current_mapping_start'] = start
		elif self.current_mapping_action == 'Delete':
			delete_start = self.current_mapping_delete_start + mapping.page_length
			fields['current_mapping_delete_start'] = delete_start

		self.db_set(fields, notify=True, commit=True)
		frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping')

	def run_current_mapping(self):
		try:
			mapping = self.get_mapping(self.current_mapping)

			if mapping.mapping_type == 'Push':
				done = self.push()
			elif mapping.mapping_type == 'Pull':
				done = self.pull()

			if done:
				self.enqueue_next_mapping()
			else:
				self.enqueue_next_page()

		except Exception as e:
			self.db_set('status', 'Error', notify=True, commit=True)
			raise e

	def get_last_modified_condition(self):
		last_run_timestamp = frappe.db.get_value('Data Migration Run', dict(
			data_migration_plan=self.data_migration_plan,
			name=('!=', self.name)
		), 'modified')
		if last_run_timestamp:
			condition = dict(modified=('>', last_run_timestamp))
		else:
			condition = None
		return condition

	def begin(self):
		self.mappings = [frappe.get_doc(
			'Data Migration Mapping', m.mapping) for m in self.get_plan().mappings]
		total_pages = 0
		for m in self.mappings:
			page_count = float(self.get_count(m)) / m.page_length
			total_pages += page_count
		self.db_set(dict(
			status = 'Started',
			current_mapping = None,
			current_mapping_start = 0,
			current_mapping_delete_start = 0,
			percent_complete = 0,
			current_mapping_action = 'Insert',
			total_pages = total_pages
		), notify=True, commit=True)

	def complete(self):
		self.db_set(dict(
			status='Success',
			percent_complete=100
		), notify=True, commit=True)

	def get_plan(self):
		if not hasattr(self, 'plan'):
			self.plan = frappe.get_doc('Data Migration Plan', self.data_migration_plan)
		return self.plan

	def get_mapping(self, mapping_name):
		if hasattr(self, 'mappings'):
			for m in self.mappings:
				if m.name == mapping_name:
					return m
		return frappe.get_doc('Data Migration Mapping', mapping_name)

	def get_next_mapping_and_percent_mappings_complete(self):
		plan = self.get_plan()
		if not self.current_mapping:
			# first
			return plan.mappings[0].mapping, 0
		for i, d in enumerate(plan.mappings):
			if i == len(plan.mappings) - 1:
				# last
				return None, 100
			if d.mapping == self.current_mapping:
				return plan.mappings[i+1].mapping, (i + 1) * 100 / len(plan.mappings)

		raise frappe.ValidationError('Mapping Broken')

	def get_data(self, mapping, start=0, condition=None):
		filters = mapping.get_filters() or {}
		if condition:
			filters.update(condition)

		if self.current_mapping_action == 'Insert':
			return frappe.get_all(mapping.local_doctype, fields=mapping.get_fields(), filters=filters, start=start,
				page_length=mapping.page_length)
		elif self.current_mapping_action == 'Delete':
			return self.get_deleted_docs(mapping,
				start=self.current_mapping_delete_start,
				page_length=mapping.page_length
			)

	def get_deleted_docs(self, mapping, start, page_length):
		filters = self.get_last_modified_condition()
		filters.update(dict(
			deleted_doctype=mapping.local_doctype
		))
		data = frappe.get_all('Deleted Document', fields=['data'], filters=filters, debug=True)

		_data = []
		for d in data:
			doc = json.loads(d.data)
			if doc.get(mapping.migration_id_field):
				doc['to_delete'] = 1
				_data.append(doc)

		return _data


	def get_count(self, mapping):
		filters = mapping.get_filters() or {}
		return frappe.get_all(mapping.local_doctype, ['count(name) as total'], filters=filters)[0].total

	def get_connection(self):
		if not hasattr(self, 'connection'):
			self.connection = frappe.get_doc('Data Migration Connector',
				self.get_plan().connector).get_connection()

		return self.connection

	def push(self):
		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start
		condition = self.get_last_modified_condition()
		connection = self.get_connection()

		data = self.get_data(mapping, start, condition)

		failed_items = json.loads(self.failed_log or '[]')

		for d in data:
			migration_id_value = d.get(mapping.migration_id_field)

			if d.get('to_delete'):
				response = connection.delete(mapping.remote_objectname, migration_id_value)
				if not response.ok:
					failed_items.append(d)
			else:
				response = connection.push(mapping.remote_objectname,
					mapping.get_mapped_record(d), migration_id_value)
				if response.ok:
					if not migration_id_value:
						frappe.db.set_value(mapping.local_doctype, d.name,
							mapping.migration_id_field, response.doc['name'],
							update_modified=False)
						frappe.db.commit()
				else:
					failed_items.append(response.doc)

		self.db_set('failed_log', json.dumps(failed_items))

		if len(data) < mapping.page_length:
			if self.current_mapping_action == 'Insert':
				self.db_set('current_mapping_action', 'Delete')
				return False
			elif self.current_mapping_action == 'Delete':
				return True

		return False

	def pull(self):
		pass