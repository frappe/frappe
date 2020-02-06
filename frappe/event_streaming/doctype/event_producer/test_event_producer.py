# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import time
from frappe.frappeclient import FrappeClient
from frappe.event_streaming.doctype.event_producer.event_producer import pull_from_node

def create_event_producer(producer_url):
	event_producer = frappe.new_doc('Event Producer')
	event_producer.producer_url = producer_url
	event_producer.append('producer_doctypes', {
		'ref_doctype': 'ToDo',
		'use_same_name': 1
	})
	event_producer.append('producer_doctypes', {
		'ref_doctype': 'Note',
		'use_same_name': 1
	})
	event_producer.user = 'Administrator'
	event_producer.insert()

class TestEventProducer(unittest.TestCase):
	def setUp(self):
		self.producer_url = 'http://test_site_producer:8000'
		if not frappe.db.exists('Event Producer', self.producer_url):
			create_event_producer(self.producer_url)
		frappe.db.sql('delete from tabToDo')
		frappe.db.sql('delete from tabNote')

	def test_insert(self):
		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test creation 1 sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))

	def test_update(self):
		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test update 1')
		producer_doc['description'] = 'test update 2'
		producer_doc = producer.update(producer_doc)
		self.pull_producer_data()
		local_doc = frappe.get_doc(producer_doc.doctype, producer_doc.name)
		self.assertEqual(local_doc.description, producer_doc.description)

	def test_delete(self):
		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test delete sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))
		producer.delete('ToDo', producer_doc.name)
		self.pull_producer_data()
		self.assertFalse(frappe.db.exists('ToDo', producer_doc.name))

	def test_multiple_doctypes_sync(self):
		producer = self.get_remote_site()

		#insert todo and note in producer
		producer_todo = insert_into_producer(producer, 'test multiple doc sync')
		producer_note1 = frappe.get_doc(dict(doctype='Note', title='test multiple doc sync 1'))
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note1.title})
		frappe.db.delete('Note', {'title': producer_note1.title})
		producer_note1 = producer.insert(producer_note1)
		producer_note2 = frappe.get_doc(dict(doctype='Note', title='test multiple doc sync 2'))
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note2.title})
		frappe.db.delete('Note', {'title': producer_note2.title})
		producer_note2 = producer.insert(producer_note2)

		#update in producer
		producer_todo['description'] = 'test multiple doc update sync'
		producer_todo = producer.update(producer_todo)
		producer_note1['content'] = 'testing update sync'
		producer_note1 = producer.update(producer_note1)

		producer.delete('Note', producer_note2.name)

		self.pull_producer_data()

		#check inserted
		self.assertTrue(frappe.db.exists('ToDo', producer_todo.name))

		#check update
		local_todo = frappe.get_doc('ToDo', producer_todo.name)
		self.assertEqual(local_todo.description, producer_todo.description)
		local_note1 = frappe.get_doc('Note', producer_note1.name)
		self.assertEqual(local_note1.content, producer_note1.content)

		#check delete
		self.assertFalse(frappe.db.exists('Note', producer_note2.name))

	def test_child_table_sync_with_dependencies(self):
		producer = self.get_remote_site()
		producer_user = frappe.get_doc(dict(doctype='User', email='test_user@sync.com', first_name='Test Sync User'))
		delete_on_remote_if_exists(producer, 'User', {'email': producer_user.email})
		frappe.db.delete('User', {'email':producer_user.email})
		producer_user.enabled = 1
		producer_user.append('roles', {
			'role': 'System Manager'
		})
		producer_user = producer.insert(producer_user)
		producer_note = frappe.get_doc(dict(doctype='Note', title='test child table dependency sync'))
		producer_note.append('seen_by', {
			'user': producer_user.name
		})
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note.title})
		frappe.db.delete('Note', {'title': producer_note.title})
		producer_note = producer.insert(producer_note)
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('User', producer_user.name))
		if self.assertTrue(frappe.db.exists('Note', producer_note.name)):
			local_note = frappe.get_doc('Note', producer_note.name)
			self.assertEqual(len(local_note.seen_by), 1)

	def test_dynamic_link_dependencies_synced(self):
		#unsubscribe for Note to check whether dependency is fulfilled
		event_producer = frappe.get_doc('Event Producer', self.producer_url)
		event_producer.producer_doctypes = []
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 1
		})
		event_producer.save()

		producer = self.get_remote_site()
		producer_link_doc = frappe.get_doc(dict(doctype='Note', title='Test Dynamic Link 1'))

		delete_on_remote_if_exists(producer, 'Note', {'title': producer_link_doc.title})
		frappe.db.delete('Note', {'title': producer_link_doc.title})
		producer_link_doc = producer.insert(producer_link_doc)
		producer_doc = frappe.get_doc(dict(doctype='ToDo', description='Test Dynamic Link 2', assigned_by='Administrator',
				reference_type='Note', reference_name=producer_link_doc.name))
		producer_doc = producer.insert(producer_doc)

		self.pull_producer_data()

		#check dynamic link dependency created
		self.assertTrue(frappe.db.exists('Note', producer_link_doc.name))
		self.assertEqual(producer_link_doc.name, frappe.db.get_value('ToDo', producer_doc.name, 'reference_name'))

		#subscribe again
		event_producer = frappe.get_doc('Event Producer', self.producer_url)
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'Note',
			'use_same_name': 1
		})
		event_producer.save()

	def test_naming_configuration(self):
		#test with use_same_name = 0
		event_producer = frappe.get_doc('Event Producer', self.producer_url)
		event_producer.producer_doctypes = []
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 0
		})
		event_producer.save()

		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test different name sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', {'remote_docname': producer_doc.name, 'remote_site_name': self.producer_url}))

		event_producer = frappe.get_doc('Event Producer', self.producer_url)
		event_producer.producer_doctypes = []
		#set use_same_name back to 1
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 1
		})
		event_producer.save()

	def test_update_log(self):
		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test update log')
		update_log_doc = producer.get_value('Event Update Log', 'docname', {'docname': producer_doc.get('name')})
		self.assertEqual(update_log_doc.get('docname'), producer_doc.get('name'))

	def test_event_sync_log(self):
		producer = self.get_remote_site()
		producer_doc = insert_into_producer(producer, 'test event sync log')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('Event Sync Log', {'docname': producer_doc.name}))

	def pull_producer_data(self):
		pull_from_node(self.producer_url)
		time.sleep(1)

	def get_remote_site(self):
		producer_doc = frappe.get_doc('Event Producer', self.producer_url)
		producer_site = FrappeClient(
			url=producer_doc.producer_url,
			api_key=producer_doc.api_key,
			api_secret=producer_doc.get_password('api_secret'),
			frappe_authorization_source='Event Consumer'
		)
		return producer_site

def insert_into_producer(producer, description):
		#create and insert todo on remote site
		todo = frappe.get_doc(dict(doctype='ToDo', description=description, assigned_by='Administrator'))
		return producer.insert(todo)

def delete_on_remote_if_exists(producer, doctype, filters):
	remote_doc = producer.get_value(doctype, 'name', filters)
	if remote_doc:
		producer.delete(doctype, remote_doc.get('name'))