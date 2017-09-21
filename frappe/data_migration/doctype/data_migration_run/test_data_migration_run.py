# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals
import frappe, unittest
from frappe.utils import today

class TestDataMigrationRun(unittest.TestCase):

	def test_run(self):
		self.create_plan()

		description = 'Data migration todo'

		new_todo = frappe.get_doc({
			'doctype': 'ToDo',
			'description': description
		}).insert()

		task_subject = 'Data migration task'
		new_task = frappe.get_doc({
			'doctype': 'Task',
			'subject': task_subject,
			'exp_start_date': today()
		}).insert()

		run = frappe.get_doc({
			'doctype': 'Data Migration Run',
			'data_migration_plan': 'Event Sync',
			'data_migration_connector': 'Local Connector'
		}).insert()

		run.run()
		self.assertEqual(run.db_get('status'), 'Success')
		self.assertEqual(run.db_get('items_inserted'), frappe.db.count('ToDo',
			filters={'todo_sync_id': ('!=', '')}))

		todo = frappe.get_doc('ToDo', new_todo.name)
		self.assertTrue(todo.todo_sync_id)

		todo_event = frappe.get_doc('Event', todo.todo_sync_id)
		self.assertEqual(todo_event.subject, description)

		task_event = frappe.get_doc('Event', {'subject': task_subject})
		self.assertEqual(task_event.subject, task_subject)

	def test_push_update(self):
		todo_list = frappe.get_list('ToDo', filters={'description': 'Data migration todo'}, fields=['name'])
		todo_name = todo_list[0].name

		todo = frappe.get_doc('ToDo', todo_name)
		todo.description = 'Data migration todo updated'
		todo.save()

		run = frappe.get_doc({
			'doctype': 'Data Migration Run',
			'data_migration_plan': 'Event Sync',
			'data_migration_connector': 'Local Connector'
		}).insert()

		run.run()
		self.assertEqual(run.db_get('status'), 'Success')
		self.assertEqual(run.db_get('items_updated'), 1)

	def create_plan(self):
		frappe.get_doc({
			'doctype': 'Data Migration Mapping',
			'mapping_name': 'Todo to Event',
			'remote_objectname': 'Event',
			'remote_primary_key': 'name',
			'local_doctype': 'ToDo',
			'mapping_type': 'Push',
			'module': 'Core',
			'fields': [
				{ 'remote_fieldname': 'subject', 'local_fieldname': 'description' },
				{ 'remote_fieldname': 'starts_on', 'local_fieldname': 'eval:frappe.utils.get_datetime_str(frappe.utils.get_datetime())' }
			]
		}).insert()

		frappe.get_doc({
			'doctype': 'Data Migration Mapping',
			'mapping_name': 'Task to Event',
			'remote_objectname': 'Task',
			'remote_primary_key': 'name',
			'local_doctype': 'Event',
			'mapping_type': 'Pull',
			'module': 'Core',
			'fields': [
				{ 'remote_fieldname': 'subject', 'local_fieldname': 'subject' },
				{ 'remote_fieldname': 'exp_start_date', 'local_fieldname': 'starts_on' },
				{ 'remote_fieldname': "Public", 'local_fieldname': 'event_type' }
			]
		}).insert()

		frappe.get_doc({
			'doctype': 'Data Migration Plan',
			'plan_name': 'Event sync',
			'module': 'Core',
			'mappings': [
				{ 'mapping': 'Todo to Event' },
				{ 'mapping': 'Task to Event' }
			]
		}).insert()

		frappe.get_doc({
			'doctype': 'Data Migration Connector',
			'connector_name': 'Local Connector',
			'connector_type': 'Frappe',
			'hostname': 'http://localhost:8000',
			'username': 'Administrator',
			'password': 'admin'
		}).insert()

