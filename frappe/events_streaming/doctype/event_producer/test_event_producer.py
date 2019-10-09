# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import time
from frappe import _
from frappe.frappeclient import FrappeClient
from frappe.events_streaming.doctype.event_producer.event_producer import pull_from_node, get_current_node

def create_event_producer():
	event_producer = frappe.new_doc('Event Producer')
	event_producer.producer_url = 'http://test_site_2:8000'
	event_producer.append('event_configuration', {
		'ref_doctype': 'ToDo',
		'use_same_name': 1
	})
	event_producer.user = 'Administrator'
	event_producer.insert()

class TestEventProducer(unittest.TestCase):
	def setUp(self):
		if not frappe.db.exists('Event Producer', 'http://test_site_2:8000'):
			create_event_producer()
		frappe.db.sql('delete from tabToDo')
		frappe.db.sql('delete from tabNote')

	def test_insert(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test creation 1 sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))
		
	def test_update(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test update 1')
		producer_doc['description'] = 'test update 2'
		producer_doc = producer.update(producer_doc)
		self.pull_producer_data()
		local_doc = frappe.get_doc(producer_doc.doctype, producer_doc.name)
		self.assertEqual(local_doc.description, producer_doc.description)

	def test_delete(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test delete sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))
		producer.delete('ToDo', producer_doc.name)
		self.pull_producer_data()
		self.assertFalse(frappe.db.exists('ToDo', producer_doc.name))

	def test_multiple_doctypes_sync(self):
		self.subscribe_to_doctypes(['ToDo', 'Note'])
		producer = get_remote_site()

		#insert todo and note in producer
		producer_todo = self.insert_into_producer(producer, 'test multiple doc sync')
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
		self.subscribe_to_doctypes(['User'])
		producer = get_remote_site()
		producer_user = frappe.get_doc(dict(doctype='User', email='test_user@sync.com', first_name='Test Sync User'))
		delete_on_remote_if_exists(producer, 'User', {'email': 'test_user@sync.com'})
		frappe.db.delete('User', {'email': producer_user.email})
		frappe.db.delete('Email Account', {'email_id': 'test-password1@example.com'})
		email_account = make_email_account_in_producer(producer, _('_Test Sync Email Account 1'), _('test-password1@example.com'))
		producer_user.user_emails = []
		producer_user.append('user_emails', {
			'email_account': email_account.name
		})
		producer_user = producer.insert(producer_user)
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('Email Account', email_account.name))
		if self.assertTrue(frappe.db.exists('User', producer_user.name)):
			local_user = frappe.get_doc('User', producer_user.name)
			self.assertEqual(len(local_user.user_emails), 3)

	def test_dynamic_link_dependencies_synced(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_link_doc = frappe.get_doc(dict(doctype='Note', title='Test Dynamic Link 1'))

		delete_on_remote_if_exists(producer, 'Note', {'title': producer_link_doc.title})
		frappe.db.delete('Note', {'title': producer_link_doc.title})
		producer_link_doc = producer.insert(producer_link_doc)
		producer_doc = frappe.get_doc(dict(doctype='ToDo', description='Test Dynamic Link 2', assigned_by='Administrator', reference_type='Note', reference_name=producer_link_doc.name))
		producer_doc = producer.insert(producer_doc)

		self.pull_producer_data()

		#check dynamic link dependency created
		self.assertTrue(frappe.db.exists('Note', producer_link_doc.name))
		self.assertEqual(producer_link_doc.name, frappe.db.get_value('ToDo', producer_doc.name, 'reference_name'))

	def test_naming_configuration(self):
		#test with use_same_name = 0
		frappe.clear_cache(doctype='ToDo')
		event_producer = frappe.get_doc('Event Producer', 'http://test_site_2:8000')
		event_producer.event_configuration = []
		event_producer.append('event_configuration', {
			'ref_doctype': 'ToDo'
		})
		event_producer.save()
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test different name sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', {'remote_docname': producer_doc.name, 'remote_site_name': 'http://test_site_2:8000'}))

	def test_update_log(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test update log')
		update_log_doc = producer.get_value('Update Log', 'docname', {'docname': producer_doc.get('name')})
		self.assertEqual(update_log_doc.get('docname'), producer_doc.get('name'))

	def test_event_sync_log(self):
		self.subscribe_to_doctypes(['ToDo'])
		producer = get_remote_site()
		producer_doc = self.insert_into_producer(producer, 'test event sync log')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('Event Sync Log', {'docname': producer_doc.name}))

	def subscribe_to_doctypes(self, doctypes):
		frappe.clear_cache(doctype='ToDo')
		event_producer = frappe.get_doc('Event Producer', 'http://test_site_2:8000')
		event_producer.event_configuration = []
		for d in doctypes:
			event_producer.append('event_configuration', {
				'ref_doctype': d,
				'use_same_name': 1
			})
		event_producer.save()

	def insert_into_producer(self, producer, description):
		#create and insert todo on remote site
		todo = frappe.get_doc(dict(doctype='ToDo', description=description, assigned_by='Administrator'))
		return producer.insert(todo)

	def pull_producer_data(self):
		pull_from_node('http://test_site_2:8000')
		time.sleep(1)

def make_email_account_in_producer(producer, name, email_id):
	delete_on_remote_if_exists(producer, 'Email Account', {'email_id': email_id})
	doc = frappe.get_doc(dict(
		doctype='Email Account',
		domain='example.com',
		email_account_name=name,
		append_to='Communication',
		smtp_server='test.example.com',
		pop3_server='pop.test.example.com',
		email_id=email_id,
		password='password',
	))
	return producer.insert(doc)

def get_remote_site():
	producer_doc = frappe.get_doc('Event Producer', 'http://test_site_2:8000')
	producer_site = FrappeClient(
		url=producer_doc.producer_url,
		api_key=producer_doc.api_key,
		api_secret=producer_doc.get_password('api_secret'),
		frappe_authorization_source='Event Consumer'
	)
	return producer_site

def delete_on_remote_if_exists(producer, doctype, filters):
	remote_doc = producer.get_value(doctype, 'name', filters)
	if remote_doc:
		producer.delete(doctype, remote_doc.get('name'))