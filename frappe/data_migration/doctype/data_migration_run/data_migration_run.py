# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class DataMigrationRun(Document):
	def get_connection(self):
		if not hasattr(self, 'connection'):
			self.connection = frappe.get_doc('Data Migration Connector',
				self.data_migration_connector).get_connection()

		return self.connection

	def validate(self):
		exists = frappe.db.exists('Data Migration Run', dict(
			status=('in', ['Fail', 'Error'])
		))
		if exists:
			frappe.throw(_('There are failed runs with the same Data Migration Plan'))

	def run(self):
		no_of_mappings = len(frappe.get_doc('Data Migration Plan',
			self.data_migration_plan).mappings)
		self.db_set(dict(
			status = 'Started',
			current_mapping = None,
			current_mapping_start = 0,
			current_mapping_pages = 0,
			no_of_mappings = no_of_mappings
		), notify=True, commit=True)
		self.enqueue_next_mapping()

	def enqueue_next_mapping(self):
		next_mapping_name, percent_mappings_complete = self.get_next_mapping_and_percent_mappings_complete()
		if next_mapping_name:
			next_mapping = frappe.get_doc('Data Migration Mapping', next_mapping_name)
			self.db_set(dict(
				current_mapping = next_mapping.name,
				current_mapping_start = 0,
				current_mapping_pages = float(next_mapping.get_data(count=True,
					condition=self.get_last_modified_condition())) / next_mapping.page_length,
				percent_complete = percent_mappings_complete
			), notify=True, commit=True)
			frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping')
		else:
			self.complete()

	def enqueue_next_page(self, start):
		self.db_set(dict(
			current_mapping_start = start,
			percent_complete = self.percent_complete + (100.0 / self.no_of_mappings / self.current_mapping_pages)
		), notify=True, commit=True)
		frappe.enqueue_doc(self.doctype, self.name, 'run_current_mapping')

	def run_current_mapping(self):
		try:
			mapping = frappe.get_doc('Data Migration Mapping', self.current_mapping)
			mapping.run_mapping(self, condition=self.get_last_modified_condition())
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

	def complete(self):
		self.db_set(dict(
			status='Success',
			percent_complete=100
		), notify=True, commit=True)

	def get_next_mapping_and_percent_mappings_complete(self):
		plan = frappe.get_doc('Data Migration Plan', self.data_migration_plan)
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
