# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json, math
from frappe.model.document import Document
from frappe import _
from frappe.utils import cint

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
			percent_complete = self.percent_complete + (100.0 / self.total_pages)
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
			total_pages = total_pages
		), notify=True, commit=True)

	def complete(self):
		fields = dict()

		failed_items = self.get_log('failed_items', [])
		if failed_items:
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

	def get_data(self, filters, or_filters, start, page_length):
		mapping = self.get_mapping(self.current_mapping)
		or_filters = self.get_or_filters(mapping)
		start = self.current_mapping_start

		data = []
		doclist = frappe.get_all(mapping.local_doctype,
			filters=filters, or_filters=or_filters,
			start=start, page_length=mapping.page_length, debug=True)

		for d in doclist:
			doc = frappe.get_doc(mapping.local_doctype, d['name'])
			data.append(doc.as_dict())
		return data

	def get_new_local_data(self):
		'''Fetch newly inserted local data using `frappe.get_all`. Used during Push'''
		mapping = self.get_mapping(self.current_mapping)
		filters = mapping.get_filters() or {}

		# new docs dont have migration field set
		filters.update({
			mapping.migration_id_field: ''
		})

		return self.get_data(filters)

	def get_updated_local_data(self):
		'''Fetch local updated data using `frappe.get_all`. Used during Push'''
		mapping = self.get_mapping(self.current_mapping)
		filters = mapping.get_filters() or {}

		# existing docs must have migration field set
		filters.update({
			mapping.migration_id_field: ('!=', '')
		})

		return self.get_data(filters)

	def get_deleted_local_data(self):
		'''Fetch local deleted data using `frappe.get_all`. Used during Push'''
		mapping = self.get_mapping(self.current_mapping)
		filters = dict(
			deleted_doctype=mapping.local_doctype
		)

		data = frappe.get_all('Deleted Document', fields=['data'],
			filters=filters, or_filters=or_filters, debug=True)

		_data = []
		for d in data:
			doc = json.loads(d.data)
			if doc.get(mapping.migration_id_field):
				doc['_deleted_document_name'] = d.name
				_data.append(doc)

		return _data


	def get_remote_data(self, mapping, start=0):
		'''Fetch data from remote using `connection.get_list`. Used during Pull'''
		filters = mapping.get_filters() or {}
		connection = self.get_connection()

		return connection.get_list(mapping.remote_objectname,
			fields=["*"], filters=filters, start=start,
			page_length=mapping.page_length)

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
		connection = self.get_connection()

		if self.current_mapping_action == 'Insert':
			data = self.get_new_local_data()

			for d in data:
				# pre process before insert
				doc = self.pre_process_doc(d)
				doc = mapping.get_mapped_record(d)

				try:
					response_doc = connection.insert(mapping.remote_objectname, doc)
					# TODO: log
					frappe.db.set_value(mapping.local_doctype, d.name,
							mapping.migration_id_field, response.migration_id_value,
							update_modified=False)
						frappe.db.commit()
					# post process only when action is success
					self.post_process_doc(local_doc=doc)
				except Exception:
					# TODO: log
					pass

			# update page_start
			self.db_set('current_mapping_start',
				self.current_mapping_start + mapping.page_length)

			if len(data) < mapping.page_length:
				# done, no more new data to insert
				self.db_set({
					'current_mapping_action': 'Update',
					'current_mapping_start': 0
				})
				# not done with this mapping
				return False

		elif self.current_mapping_action == 'Update':
			data = self.get_updated_local_data()

			for d in data:
				migration_id_value = d.get(mapping.migration_id_field)
				# pre process before update
				doc = self.pre_process_doc(d)
				doc = mapping.get_mapped_record(d)
				try:
					response = connection.update(mapping.remote_objectname, doc, migration_id_value)
					# post process only when action is success
					self.post_process_doc(local_doc=doc)
					# TODO: log
				except Exception:
					# TODO: log
					pass

			# update page_start
			self.db_set('current_mapping_start',
				self.current_mapping_start + mapping.page_length)

			if len(data) < mapping.page_length:
				# done, no more data to update
				self.db_set({
					'current_mapping_action': 'Delete',
					'current_mapping_start': 0
				})
				# not done with this mapping
				return False

		elif self.current_mapping_action == 'Delete':
			data = self.get_deleted_local_data()

			for d in data:
				# Deleted Document also has a custom field for migration_id
				migration_id_value = d.get(mapping.migration_id_field)
				# pre process before update
				doc = self.pre_process_doc(d)
				try:
					response = connection.delete(mapping.remote_objectname, migration_id_value)
					# post process only when action is success
					self.post_process_doc(local_doc=doc)
					# TODO: log
				except Exception:
					# TODO: log
					pass

			# update page_start
			self.db_set('current_mapping_start',
				self.current_mapping_start + mapping.page_length)

			if len(data) < mapping.page_length:
				# done, no more new data to delete
				# done with this mapping
				return True

		# just because
		return True

		# data = self.get_local_data()

		# failed_items = self.get_log('failed_items', [])

		# for d in data:
		# 	migration_id_value = d.get(mapping.migration_id_field)

		# 	if d.get('to_delete'):
		# 		# local doc deleted, delete from remote
		# 		response = connection.delete(mapping.remote_objectname, migration_id_value)
		# 		if not response.ok:
		# 			failed_items.append(d)
		# 		else:
		# 			self.set_log('push:deleted_items', cint(self.get_log('push:deleted_items', 0)) + 1)
		# 			frappe.db.set_value('Deleted Document',
		# 				d.get('_deleted_document_name'),
		# 				mapping.migration_id_field, migration_id_value,
		# 				update_modified=False)
		# 	else:
		# 		doc = mapping.get_mapped_record(d)

		# 		# pre process before insert/update
		# 		doc = self.pre_process_doc(doc)

		# 		if not migration_id_value:
		# 			# no migration_id_value, insert doc
		# 			response = connection.insert(
		# 				mapping.remote_objectname, doc)
		# 		else:
		# 			# migration_id_value exists, update doc
		# 			response = connection.update(
		# 				mapping.remote_objectname, doc, migration_id_value)

		# 		if not response.ok:
		# 			# insert/update fail
		# 			failed_items.append(doc)
		# 		else:
		# 			# insert/update success
		# 			if not migration_id_value:
		# 				self.set_log('push:insert', cint(self.get_log('push:insert', 0)) + 1)

		# 				frappe.db.set_value(mapping.local_doctype, d.name,
		# 					mapping.migration_id_field, response.migration_id_value,
		# 					update_modified=False)
		# 				frappe.db.commit()
		# 			else:
		# 				self.set_log('push:update', cint(self.get_log('push:update', 0)) + 1)

		# 			# post process only when action is success
		# 			self.post_process_doc(local_doc=doc)

		# self.set_log('failed_items', failed_items)

		# if len(data) < mapping.page_length:
		# 	if self.current_mapping_action == 'Insert':
		# 		self.db_set('current_mapping_action', 'Delete')
		# 		return False
		# 	elif self.current_mapping_action == 'Delete':
		# 		return True

		# return False

	def pull(self):
		self.db_set('current_mapping_type', 'Pull')

		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start

		failed_items = self.get_log('failed_items', [])

		response = self.get_remote_data(mapping, start)
		if response.ok and response.data:
			data = response.data

			for d in data:
				migration_id_value = d[response.migration_id_field]
				doc = self.pre_process_doc(d)
				doc = mapping.get_mapped_record(doc)

				if migration_id_value:
					if not local_doc_exists(mapping, migration_id_value):
						# insert new local doc
						local_doc = insert_doc(mapping, doc)

						self.set_log('pull:insert', cint(self.get_log('pull:insert', 0)) + 1)

						# set migration id
						frappe.db.set_value(mapping.local_doctype, local_doc.name,
							mapping.migration_id_field, migration_id_value,
							update_modified=False)
						frappe.db.commit()
					else:
						# update doc
						local_doc = update_doc(mapping, doc, migration_id_value)

						self.set_log('pull:update', cint(self.get_log('pull:update', 0)) + 1)

				if local_doc:
					# post process doc after success
					self.post_process_doc(remote_doc=d, local_doc=local_doc)
				else:
					# failed, append to log
					failed_items.append(d)

			self.set_log('failed_items', failed_items)

			if len(data) < mapping.page_length:
				# last page, done with pull
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

	def set_log(self, key, value):
		log = json.loads(self.db_get('log') or '{}')
		log[key] = value
		self.db_set('log', json.dumps(log))

	def get_log(self, key, default=None):
		log = json.loads(self.db_get('log') or '{}')
		return log.get(key, default)

def insert_doc(mapping, doc):
	try:
		# insert new doc
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
