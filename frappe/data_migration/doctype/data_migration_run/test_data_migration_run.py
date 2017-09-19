# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
import frappe, unittest

class TestDataMigrationRun(unittest.TestCase):

	def test_push(self):
		self.create_plan()

		description = 'Data migration todo'
		new_todo = frappe.get_doc({
			'doctype': 'ToDo',
			'description': description
		}).insert()

		run = frappe.get_doc({
			'doctype': 'Data Migration Run',
			'data_migration_plan': 'ToDo Sync',
			'data_migration_connector': 'Local Connector'
		}).insert()

		run.run()
		self.assertEqual(run.db_get('status'), 'Success')
		self.assertEqual(run.db_get('items_inserted'), 1)

		todo = frappe.get_doc('ToDo', new_todo.name)
		self.assertEqual(todo.todo_sync_id, description)

		note = frappe.get_doc('Note', description)
		self.assertEqual(note.title, description)

	def test_push_update(self):
		todo_list = frappe.get_list('ToDo', filters={'description': 'Data migration todo'}, fields=['name'])
		todo_name = todo_list[0].name

		todo = frappe.get_doc('ToDo', todo_name)
		todo.description = 'Data migration todo updated'
		todo.save()

		run = frappe.get_doc({
			'doctype': 'Data Migration Run',
			'data_migration_plan': 'ToDo Sync',
			'data_migration_connector': 'Local Connector'
		}).insert()

		run.run()
		self.assertEqual(run.db_get('status'), 'Success')
		self.assertEqual(run.db_get('items_updated'), 1)

	def create_plan(self):
		frappe.get_doc({
			'doctype': 'Data Migration Mapping',
			'mapping_name': 'Todo to Note',
			'remote_objectname': 'Note',
			'remote_primary_key': 'title',
			'local_doctype': 'ToDo',
			'fields': [
				{ 'remote_fieldname': 'title', 'local_fieldname': 'description' }
			]
		}).insert()

		frappe.get_doc({
			'doctype': 'Data Migration Plan',
			'plan_name': 'ToDo sync',
			'module': 'Core',
			'mappings': [
				{ 'mapping': 'Todo to Note' }
			]
		}).insert()

		frappe.get_doc({
			'doctype': 'Data Migration Connector',
			'connector_name': 'Local Connector',
			'connector_type': 'Frappe',
			'hostname': 'localhost:8000',
			'username': 'Administrator',
			'password': 'admin'
		}).insert()

