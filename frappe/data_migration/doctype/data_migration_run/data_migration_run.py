# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json
import math

import frappe
from frappe import _
from frappe.data_migration.doctype.data_migration_mapping.data_migration_mapping import (
	get_source_value,
)
from frappe.model.document import Document
from frappe.utils import cstr


class DataMigrationRun(Document):
	@frappe.whitelist()
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
			self.db_set(
				dict(
					current_mapping=next_mapping.name,
					current_mapping_start=0,
					current_mapping_delete_start=0,
					current_mapping_action="Insert",
				),
				notify=True,
				commit=True,
			)
			frappe.enqueue_doc(self.doctype, self.name, "run_current_mapping", now=frappe.flags.in_test)
		else:
			self.complete()

	def enqueue_next_page(self):
		mapping = self.get_mapping(self.current_mapping)
		percent_complete = self.percent_complete + (100.0 / self.total_pages)
		fields = dict(percent_complete=percent_complete)
		if self.current_mapping_action == "Insert":
			start = self.current_mapping_start + mapping.page_length
			fields["current_mapping_start"] = start
		elif self.current_mapping_action == "Delete":
			delete_start = self.current_mapping_delete_start + mapping.page_length
			fields["current_mapping_delete_start"] = delete_start

		self.db_set(fields, notify=True, commit=True)

		if percent_complete < 100:
			frappe.publish_realtime(
				self.trigger_name, {"progress_percent": percent_complete}, user=frappe.session.user
			)

		frappe.enqueue_doc(self.doctype, self.name, "run_current_mapping", now=frappe.flags.in_test)

	def run_current_mapping(self):
		try:
			mapping = self.get_mapping(self.current_mapping)

			if mapping.mapping_type == "Push":
				done = self.push()
			elif mapping.mapping_type == "Pull":
				done = self.pull()

			if done:
				self.enqueue_next_mapping()
			else:
				self.enqueue_next_page()

		except Exception as e:
			self.db_set("status", "Error", notify=True, commit=True)
			print("Data Migration Run failed")
			print(frappe.get_traceback())
			self.execute_postprocess("Error")
			raise e

	def get_last_modified_condition(self):
		last_run_timestamp = frappe.db.get_value(
			"Data Migration Run",
			dict(
				data_migration_plan=self.data_migration_plan,
				data_migration_connector=self.data_migration_connector,
				name=("!=", self.name),
			),
			"modified",
		)
		if last_run_timestamp:
			condition = dict(modified=(">", last_run_timestamp))
		else:
			condition = {}
		return condition

	def begin(self):
		plan_active_mappings = [m for m in self.get_plan().mappings if m.enabled]
		self.mappings = [
			frappe.get_doc("Data Migration Mapping", m.mapping) for m in plan_active_mappings
		]

		total_pages = 0
		for m in [mapping for mapping in self.mappings]:
			if m.mapping_type == "Push":
				count = float(self.get_count(m))
				page_count = math.ceil(count / m.page_length)
				total_pages += page_count
			if m.mapping_type == "Pull":
				total_pages += 10

		self.db_set(
			dict(
				status="Started",
				current_mapping=None,
				current_mapping_start=0,
				current_mapping_delete_start=0,
				percent_complete=0,
				current_mapping_action="Insert",
				total_pages=total_pages,
			),
			notify=True,
			commit=True,
		)

	def complete(self):
		fields = dict()

		push_failed = self.get_log("push_failed", [])
		pull_failed = self.get_log("pull_failed", [])

		status = "Partial Success"

		if not push_failed and not pull_failed:
			status = "Success"
			fields["percent_complete"] = 100

		fields["status"] = status

		self.db_set(fields, notify=True, commit=True)

		self.execute_postprocess(status)

		frappe.publish_realtime(self.trigger_name, {"progress_percent": 100}, user=frappe.session.user)

	def execute_postprocess(self, status):
		# Execute post process
		postprocess_method_path = self.get_plan().postprocess_method

		if postprocess_method_path:
			frappe.get_attr(postprocess_method_path)(
				{
					"status": status,
					"stats": {
						"push_insert": self.push_insert,
						"push_update": self.push_update,
						"push_delete": self.push_delete,
						"pull_insert": self.pull_insert,
						"pull_update": self.pull_update,
					},
				}
			)

	def get_plan(self):
		if not hasattr(self, "plan"):
			self.plan = frappe.get_doc("Data Migration Plan", self.data_migration_plan)
		return self.plan

	def get_mapping(self, mapping_name):
		if hasattr(self, "mappings"):
			for m in self.mappings:
				if m.name == mapping_name:
					return m
		return frappe.get_doc("Data Migration Mapping", mapping_name)

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
				return mappings[i + 1].mapping

		raise frappe.ValidationError("Mapping Broken")

	def get_data(self, filters):
		mapping = self.get_mapping(self.current_mapping)
		or_filters = self.get_or_filters(mapping)
		start = self.current_mapping_start

		data = []
		doclist = frappe.get_all(
			mapping.local_doctype,
			filters=filters,
			or_filters=or_filters,
			start=start,
			page_length=mapping.page_length,
		)

		for d in doclist:
			doc = frappe.get_doc(mapping.local_doctype, d["name"])
			data.append(doc)
		return data

	def get_new_local_data(self):
		"""Fetch newly inserted local data using `frappe.get_all`. Used during Push"""
		mapping = self.get_mapping(self.current_mapping)
		filters = mapping.get_filters() or {}

		# new docs dont have migration field set
		filters.update({mapping.migration_id_field: ""})

		return self.get_data(filters)

	def get_updated_local_data(self):
		"""Fetch local updated data using `frappe.get_all`. Used during Push"""
		mapping = self.get_mapping(self.current_mapping)
		filters = mapping.get_filters() or {}

		# existing docs must have migration field set
		filters.update({mapping.migration_id_field: ("!=", "")})

		return self.get_data(filters)

	def get_deleted_local_data(self):
		"""Fetch local deleted data using `frappe.get_all`. Used during Push"""
		mapping = self.get_mapping(self.current_mapping)
		filters = self.get_last_modified_condition()
		filters.update({"deleted_doctype": mapping.local_doctype})

		data = frappe.get_all("Deleted Document", fields=["name", "data"], filters=filters)

		_data = []
		for d in data:
			doc = json.loads(d.data)
			if doc.get(mapping.migration_id_field):
				doc["_deleted_document_name"] = d["name"]
				_data.append(doc)

		return _data

	def get_remote_data(self):
		"""Fetch data from remote using `connection.get`. Used during Pull"""
		mapping = self.get_mapping(self.current_mapping)
		start = self.current_mapping_start
		filters = mapping.get_filters() or {}
		connection = self.get_connection()

		return connection.get(
			mapping.remote_objectname,
			fields=["*"],
			filters=filters,
			start=start,
			page_length=mapping.page_length,
		)

	def get_count(self, mapping):
		filters = mapping.get_filters() or {}
		or_filters = self.get_or_filters(mapping)

		to_insert = frappe.get_all(
			mapping.local_doctype, ["count(name) as total"], filters=filters, or_filters=or_filters
		)[0].total

		to_delete = frappe.get_all(
			"Deleted Document",
			["count(name) as total"],
			filters={"deleted_doctype": mapping.local_doctype},
			or_filters=or_filters,
		)[0].total

		return to_insert + to_delete

	def get_or_filters(self, mapping):
		or_filters = self.get_last_modified_condition()

		# docs whose migration_id_field is not set
		# failed in the previous run, include those too
		or_filters.update({mapping.migration_id_field: ("=", "")})

		return or_filters

	def get_connection(self):
		if not hasattr(self, "connection"):
			self.connection = frappe.get_doc(
				"Data Migration Connector", self.data_migration_connector
			).get_connection()

		return self.connection

	def push(self):
		self.db_set("current_mapping_type", "Push")
		done = True

		if self.current_mapping_action == "Insert":
			done = self._push_insert()

		elif self.current_mapping_action == "Update":
			done = self._push_update()

		elif self.current_mapping_action == "Delete":
			done = self._push_delete()

		return done

	def _push_insert(self):
		"""Inserts new local docs on remote"""
		mapping = self.get_mapping(self.current_mapping)
		connection = self.get_connection()
		data = self.get_new_local_data()

		for d in data:
			# pre process before insert
			doc = self.pre_process_doc(d)
			doc = mapping.get_mapped_record(doc)

			try:
				response_doc = connection.insert(mapping.remote_objectname, doc)
				frappe.db.set_value(
					mapping.local_doctype,
					d.name,
					mapping.migration_id_field,
					response_doc[connection.name_field],
					update_modified=False,
				)
				frappe.db.commit()
				self.update_log("push_insert", 1)
				# post process after insert
				self.post_process_doc(local_doc=d, remote_doc=response_doc)
			except Exception as e:
				self.update_log("push_failed", {d.name: cstr(e)})

		# update page_start
		self.db_set("current_mapping_start", self.current_mapping_start + mapping.page_length)

		if len(data) < mapping.page_length:
			# done, no more new data to insert
			self.db_set({"current_mapping_action": "Update", "current_mapping_start": 0})
			# not done with this mapping
			return False

	def _push_update(self):
		"""Updates local modified docs on remote"""
		mapping = self.get_mapping(self.current_mapping)
		connection = self.get_connection()
		data = self.get_updated_local_data()

		for d in data:
			migration_id_value = d.get(mapping.migration_id_field)
			# pre process before update
			doc = self.pre_process_doc(d)
			doc = mapping.get_mapped_record(doc)
			try:
				response_doc = connection.update(mapping.remote_objectname, doc, migration_id_value)
				self.update_log("push_update", 1)
				# post process after update
				self.post_process_doc(local_doc=d, remote_doc=response_doc)
			except Exception as e:
				self.update_log("push_failed", {d.name: cstr(e)})

		# update page_start
		self.db_set("current_mapping_start", self.current_mapping_start + mapping.page_length)

		if len(data) < mapping.page_length:
			# done, no more data to update
			self.db_set({"current_mapping_action": "Delete", "current_mapping_start": 0})
			# not done with this mapping
			return False

	def _push_delete(self):
		"""Deletes docs deleted from local on remote"""
		mapping = self.get_mapping(self.current_mapping)
		connection = self.get_connection()
		data = self.get_deleted_local_data()

		for d in data:
			# Deleted Document also has a custom field for migration_id
			migration_id_value = d.get(mapping.migration_id_field)
			# pre process before update
			self.pre_process_doc(d)
			try:
				response_doc = connection.delete(mapping.remote_objectname, migration_id_value)
				self.update_log("push_delete", 1)
				# post process only when action is success
				self.post_process_doc(local_doc=d, remote_doc=response_doc)
			except Exception as e:
				self.update_log("push_failed", {d.name: cstr(e)})

		# update page_start
		self.db_set("current_mapping_start", self.current_mapping_start + mapping.page_length)

		if len(data) < mapping.page_length:
			# done, no more new data to delete
			# done with this mapping
			return True

	def pull(self):
		self.db_set("current_mapping_type", "Pull")

		connection = self.get_connection()
		mapping = self.get_mapping(self.current_mapping)
		data = self.get_remote_data()

		for d in data:
			migration_id_value = get_source_value(d, connection.name_field)
			doc = self.pre_process_doc(d)
			doc = mapping.get_mapped_record(doc)

			if migration_id_value:
				try:
					if not local_doc_exists(mapping, migration_id_value):
						# insert new local doc
						local_doc = insert_local_doc(mapping, doc)

						self.update_log("pull_insert", 1)
						# set migration id
						frappe.db.set_value(
							mapping.local_doctype,
							local_doc.name,
							mapping.migration_id_field,
							migration_id_value,
							update_modified=False,
						)
						frappe.db.commit()
					else:
						# update doc
						local_doc = update_local_doc(mapping, doc, migration_id_value)
						self.update_log("pull_update", 1)
					# post process doc after success
					self.post_process_doc(remote_doc=d, local_doc=local_doc)
				except Exception as e:
					# failed, append to log
					self.update_log("pull_failed", {migration_id_value: cstr(e)})

		if len(data) < mapping.page_length:
			# last page, done with pull
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
		value = json.dumps(value) if "_failed" in key else value
		self.db_set(key, value)

	def update_log(self, key, value=None):
		"""
		Helper for updating logs,
		push_failed and pull_failed are stored as json,
		other keys are stored as int
		"""
		if "_failed" in key:
			# json
			self.set_log(key, self.get_log(key, []) + [value])
		else:
			# int
			self.set_log(key, self.get_log(key, 0) + (value or 1))

	def get_log(self, key, default=None):
		value = self.db_get(key)
		if "_failed" in key:
			if not value:
				value = json.dumps(default)
			value = json.loads(value)
		return value or default


def insert_local_doc(mapping, doc):
	try:
		# insert new doc
		if not doc.doctype:
			doc.doctype = mapping.local_doctype
		doc = frappe.get_doc(doc).insert()
		return doc
	except Exception:
		print("Data Migration Run failed: Error in Pull insert")
		print(frappe.get_traceback())
		return None


def update_local_doc(mapping, remote_doc, migration_id_value):
	try:
		# migration id value is set in migration_id_field in mapping.local_doctype
		docname = frappe.db.get_value(
			mapping.local_doctype, filters={mapping.migration_id_field: migration_id_value}
		)

		doc = frappe.get_doc(mapping.local_doctype, docname)
		doc.update(remote_doc)
		doc.save()
		return doc
	except Exception:
		print("Data Migration Run failed: Error in Pull update")
		print(frappe.get_traceback())
		return None


def local_doc_exists(mapping, migration_id_value):
	return frappe.db.exists(mapping.local_doctype, {mapping.migration_id_field: migration_id_value})
