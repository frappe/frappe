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
			status=('in', ['Fail', 'Error']),
			name=('!=', self.name)
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
			percent_complete = self.percent_complete + (100.0 / self.total_pages),
			items_inserted=self.items_inserted,
			items_updated=self.items_updated,
			items_deleted=self.items_deleted
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
			print('Data Migration Run failed')
			print(frappe.get_traceback())
			raise e

	def get_last_modified_condition(self):
		last_run_timestamp = frappe.db.get_value('Data Migration Run', dict(
			data_migration_plan=self.data_migration_plan,
			name=('!=', self.name)
		), 'modified')
		if last_run_timestamp:
			condition = dict(modified=('>', last_run_timestamp))
		else:
			condition = {}
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
			total_pages = total_pages,
			items_inserted = 0,
			items_updated = 0,
			items_deleted = 0
		), notify=True, commit=True)

	def complete(self):
		status = 'Success'
		items_failed = json.loads(self.failed_log)
		if items_failed:
			self.items_failed = len(items_failed)
			status = 'Partial Success'
		self.db_set(dict(
			status=status,
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

	def get_data(self, mapping, start=0):
		filters = mapping.get_filters() or {}
		or_filters = self.get_last_modified_condition()

		# include docs whose migration_id_field is not set
		or_filters.update({
			mapping.migration_id_field: ('=', '')
		})

		if self.current_mapping_action == 'Insert':
			return frappe.get_all(mapping.local_doctype,
				fields=mapping.get_fields(),
				filters=filters, or_filters=or_filters,
				start=start, page_length=mapping.page_length, debug=True)
		elif self.current_mapping_action == 'Delete':
			return self.get_deleted_docs(mapping,
				start=self.current_mapping_delete_start,
				page_length=mapping.page_length,
				or_filters=or_filters
			)

	def get_deleted_docs(self, mapping, start, page_length, or_filters):
		filters = dict(
			deleted_doctype=mapping.local_doctype
		)
		data = frappe.get_all('Deleted Document', fields=['data'],
			filters=filters, or_filters=or_filters, debug=True)

		_data = []
		for d in data:
			doc = json.loads(d.data)
			if doc.get(mapping.migration_id_field):
				doc['to_delete'] = 1
				doc['_deleted_document_name'] = d.name
				_data.append(doc)

		return _data


	def get_count(self, mapping):
		filters = mapping.get_filters() or {}
		return frappe.get_all(mapping.local_doctype, ['count(name) as total'], filters=filters)[0].total

	def get_connection(self):
		if not hasattr(self, 'connection'):
			self.connection = frappe.get_doc('Data Migration Connector',
				self.data_migration_connector).get_connection()

		return self.connection

	def push(self):
		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start
		connection = self.get_connection()

		data = self.get_data(mapping, start)
		failed_items = json.loads(self.failed_log or '[]')

		for d in data:
			migration_id_value = d.get(mapping.migration_id_field)

			if d.get('to_delete'):
				response = connection.delete(mapping.remote_objectname, migration_id_value)
				if not response.ok:
					failed_items.append(d)
				else:
					self.items_deleted += 1
					frappe.db.set_value('Deleted Document',
						d.get('_deleted_document_name'),
						mapping.migration_id_field, migration_id_value,
						update_modified=False)
			else:
				if not migration_id_value:
					response = connection.insert(mapping.remote_objectname,
						mapping.get_mapped_record(d))
				else:
					response = connection.update(mapping.remote_objectname,
						mapping.get_mapped_record(d), migration_id_value)
				if response.ok:
					if not migration_id_value:
						self.items_inserted += 1
						frappe.db.set_value(mapping.local_doctype, d.name,
							mapping.migration_id_field, response.doc['name'],
							update_modified=False)
						frappe.db.commit()
					else:
						self.items_updated += 1
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