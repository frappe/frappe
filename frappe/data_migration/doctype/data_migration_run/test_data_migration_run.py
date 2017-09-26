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

		new_todo = frappe.get_doc(dict(
			doctype= 'ToDo',
			description= description
		)).insert()

		event_subject = 'Data migration event'

		new_event = frappe.get_doc(dict(
			doctype='Event',
			subject=event_subject,
			repeat_on='Every Month',
			starts_on=frappe.utils.now_datetime()
		)).insert()

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

		created_todo = frappe.get_doc('Event', todo.todo_sync_id)
		self.assertEqual(created_todo.subject, description)

		created_event = frappe.get_doc('Todo', {'description': event_subject})
		self.assertEqual(created_event.subject, event_subject)

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
			'fields': [
				{ 'remote_fieldname': 'subject', 'local_fieldname': 'description' },
				{ 'remote_fieldname': 'starts_on', 'local_fieldname': 'eval:frappe.utils.get_datetime_str(frappe.utils.get_datetime())' }
			]
		}).insert(ignore_if_duplicate=True)

		frappe.get_doc({
			'doctype': 'Data Migration Mapping',
			'mapping_name': 'Event to ToDo',
			'remote_objectname': 'Event',
			'remote_primary_key': 'name',
			'local_doctype': 'ToDo',
			'mapping_type': 'Pull',
			'fields': [
				{ 'remote_fieldname': 'description', 'local_fieldname': 'subject' }
			]
		}).insert(ignore_if_duplicate=True)

		frappe.get_doc({
			'doctype': 'Data Migration Plan',
			'plan_name': 'Event Sync',
			'module': 'Core',
			'mappings': [
				{ 'mapping': 'Todo to Event' },
				{ 'mapping': 'Event to Todo' }
			]
		}).insert(ignore_if_duplicate=True)

		frappe.get_doc({
			'doctype': 'Data Migration Connector',
			'connector_name': 'Local Connector',
			'connector_type': 'Frappe',
			'hostname': 'http://localhost:8000',
			'username': 'Administrator',
			'password': 'admin'
		}).insert(ignore_if_duplicate=True)

