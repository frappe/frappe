# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json, math
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
		if self.total_pages > 0:
			self.enqueue_next_mapping()
		else:
			self.complete()

	def enqueue_next_mapping(self):
		next_mapping_name = self.get_next_mapping_name()
		if next_mapping_name:
			next_mapping = self.get_mapping(next_mapping_name)
			self.db_set(dict(
				current_mapping = next_mapping.name,
				current_mapping_start = 0,
				current_mapping_delete_start = 0,
				current_mapping_action = 'Insert'
			), notify=True, commit=True)
			frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping', now=frappe.flags.in_test)
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
		frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping', now=frappe.flags.in_test)

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
		plan_active_mappings = [m for m in self.get_plan().mappings if m.enabled]
		self.mappings = [frappe.get_doc(
			'Data Migration Mapping', m.mapping) for m in plan_active_mappings]

		total_pages = 0
		for m in [mapping for mapping in self.mappings if mapping.mapping_type == 'Push']:
			count = float(self.get_count(m))
			page_count = math.ceil(count / m.page_length)
			total_pages += page_count

		total_pages = 10

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
		fields = dict()
		items_failed = json.loads(self.failed_log or '[]')
		if items_failed:
			self.items_failed = len(items_failed)
			fields['status'] = 'Partial Success'
		else:
			fields['status'] = 'Success'
			fields['percent_complete'] = 100

		self.db_set(fields, notify=True, commit=True)

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

	def get_next_mapping_name(self):
		mappings = [m for m in self.get_plan().mappings if m.enabled]
		if not self.current_mapping:
			# first
			return mappings[0].mapping
		for i, d in enumerate(mappings):
			if i == len(mappings) - 1:
				# last
				return None
			if d.mapping == self.current_mapping:
				return mappings[i+1].mapping

		raise frappe.ValidationError('Mapping Broken')

	def get_local_data(self, mapping, start=0):
		'''Fetch data from local using `frappe.get_all`. Used during Push'''
		filters = mapping.get_filters() or {}
		or_filters = self.get_or_filters(mapping)

		if self.current_mapping_action == 'Insert':
			return frappe.get_all(mapping.local_doctype,
				fields=mapping.get_fields(),
				filters=filters, or_filters=or_filters,
				start=start, page_length=mapping.page_length, debug=True)
		elif self.current_mapping_action == 'Delete':
			return self.get_deleted_docs(mapping,
				start=self.current_mapping_delete_start,
				page_length=mapping.page_length
			)

	def get_remote_data(self, mapping, start=0):
		'''Fetch data from remote using `connection.get_list`. Used during Pull'''
		filters = mapping.get_filters() or {}
		connection = self.get_connection()

		return connection.get_list(mapping.remote_objectname,
			fields=["*"], filters=filters, start=start,
			page_length=mapping.page_length)

	def get_deleted_docs(self, mapping, start, page_length):
		filters = dict(
			deleted_doctype=mapping.local_doctype
		)
		data = frappe.get_all('Deleted Document', fields=['data'],
			filters=filters, or_filters=self.get_or_filters(mapping), debug=True)

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
		or_filters = self.get_or_filters(mapping)

		to_insert = frappe.get_all(mapping.local_doctype, ['count(name) as total'],
			filters=filters, or_filters=or_filters)[0].total

		to_delete = frappe.get_all('Deleted Document', ['count(name) as total'],
			filters={'deleted_doctype': mapping.local_doctype}, or_filters=or_filters)[0].total

		return to_insert + to_delete

	def get_or_filters(self, mapping):
		or_filters = self.get_last_modified_condition()

		# include docs whose migration_id_field is not set
		or_filters.update({
			mapping.migration_id_field: ('=', '')
		})

		return or_filters

	def get_connection(self):
		if not hasattr(self, 'connection'):
			self.connection = frappe.get_doc('Data Migration Connector',
				self.data_migration_connector).get_connection()

		return self.connection

	def push(self):
		self.db_set('current_mapping_type', 'Push')

		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start
		connection = self.get_connection()

		data = self.get_local_data(mapping, start)
		failed_log = json.loads(self.db_get('failed_log') or '[]')

		for d in data:
			migration_id_value = d.get(mapping.migration_id_field)

			if d.get('to_delete'):
				# local doc deleted, delete from remote
				response = connection.delete(mapping.remote_objectname, migration_id_value)
				if not response.ok:
					failed_log.append(d)
				else:
					self.items_deleted += 1
					frappe.db.set_value('Deleted Document',
						d.get('_deleted_document_name'),
						mapping.migration_id_field, migration_id_value,
						update_modified=False)
			else:
				doc = mapping.get_mapped_record(d)

				# pre process before insert/update
				doc = self.pre_process_doc(doc)

				if not migration_id_value:
					# no migration_id_value, insert doc
					response = connection.insert(
						mapping.remote_objectname, doc)
				else:
					# migration_id_value exists, update doc
					response = connection.update(
						mapping.remote_objectname, doc, migration_id_value)

				if not response.ok:
					# insert/update fail
					failed_log.append(doc)
				else:
					# insert/update success
					if not migration_id_value:
						self.items_inserted += 1
						frappe.db.set_value(mapping.local_doctype, d.name,
							mapping.migration_id_field, response.migration_id_value,
							update_modified=False)
						frappe.db.commit()
					else:
						self.items_updated += 1

					# post process only when action is success
					self.post_process_doc(local_doc=doc)

		self.db_set('failed_log', json.dumps(failed_log))

		if len(data) < mapping.page_length:
			if self.current_mapping_action == 'Insert':
				self.db_set('current_mapping_action', 'Delete')
				return False
			elif self.current_mapping_action == 'Delete':
				return True

		return False

	def pull(self):
		self.db_set('current_mapping_type', 'Pull')

		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start
		failed_log = json.loads(self.db_get('failed_log') or '[]')

		response = self.get_remote_data(mapping, start)
		if response.ok and response.data:
			data = response.data

			for d in data:
				migration_id_value = d[response.migration_id_field]
				doc = self.pre_process_doc(d)

				if migration_id_value:
					if not local_doc_exists(mapping, migration_id_value):
						# insert new local doc
						local_doc = insert_doc(mapping, doc)

						# set migration id
						frappe.db.set_value(mapping.local_doctype, local_doc.name,
							mapping.migration_id_field, migration_id_value,
							update_modified=False)
						frappe.db.commit()
					else:
						# update doc
						local_doc = update_doc(mapping, doc, migration_id_value)

				if local_doc:
					# post process doc after success
					self.post_process_doc(remote_doc=d, local_doc=local_doc)
				else:
					failed_log.append(d)

			self.db_set('failed_log', json.dumps(failed_log))

			if len(data) < mapping.page_length:
				if self.current_mapping_action == 'Insert':
					self.db_set('current_mapping_action', 'Delete')
					return False
				elif self.current_mapping_action == 'Delete':
					return True

			return False

		# response not ok, skip pull
		return True

	def pre_process_doc(self, doc):
		plan = self.get_plan()
		doc = plan.pre_process_doc(self.current_mapping, doc)
		return doc

	def post_process_doc(self, local_doc=None, remote_doc=None):
		plan = self.get_plan()
		doc = plan.post_process_doc(self.current_mapping, local_doc=local_doc, remote_doc=remote_doc)
		return doc

def insert_doc(mapping, remote_doc):
	try:
		# insert new doc
		doc = mapping.get_mapped_record(remote_doc)
		if not doc.doctype:
			doc.doctype = mapping.local_doctype
		doc = frappe.get_doc(doc).insert()
		return doc
	except Exception:
		print('Data Migration Run failed: Error in Pull insert')
		print(frappe.get_traceback())
		return None

def update_doc(mapping, remote_doc, migration_id_value):
	try:
		# migration id value is set in migration_id_field in mapping.local_doctype
		docname = frappe.db.get_value(mapping.local_doctype,
			filters={ mapping.migration_id_field: migration_id_value })

		doc = frappe.get_doc(mapping.local_doctype, docname)
		doc.update(remote_doc)
		doc.save()
		return doc
	except Exception:
		print('Data Migration Run failed: Error in Pull update')
		print(frappe.get_traceback())
		return None

def local_doc_exists(mapping, migration_id_value):
	return frappe.db.exists(mapping.local_doctype, {
		mapping.migration_id_field: migration_id_value
	})
