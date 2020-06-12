# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import json
from frappe.frappeclient import FrappeClient
from frappe.event_streaming.doctype.event_producer.event_producer import pull_from_node

producer_url = 'http://test_site_producer:8000'

class TestEventProducer(unittest.TestCase):
	def setUp(self):
		create_event_producer(producer_url)

	def test_insert(self):
		producer = get_remote_site()
		producer_doc = insert_into_producer(producer, 'test creation 1 sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))

	def test_update(self):
		producer = get_remote_site()
		producer_doc = insert_into_producer(producer, 'test update 1')
		producer_doc['description'] = 'test update 2'
		producer_doc = producer.update(producer_doc)
		self.pull_producer_data()
		local_doc = frappe.get_doc(producer_doc.doctype, producer_doc.name)
		self.assertEqual(local_doc.description, producer_doc.description)

	def test_delete(self):
		producer = get_remote_site()
		producer_doc = insert_into_producer(producer, 'test delete sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', producer_doc.name))
		producer.delete('ToDo', producer_doc.name)
		self.pull_producer_data()
		self.assertFalse(frappe.db.exists('ToDo', producer_doc.name))

	def test_multiple_doctypes_sync(self):
		producer = get_remote_site()

		#insert todo and note in producer
		producer_todo = insert_into_producer(producer, 'test multiple doc sync')
		producer_note1 = frappe._dict(doctype='Note', title='test multiple doc sync 1')
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note1['title']})
		frappe.db.delete('Note', {'title': producer_note1['title']})
		producer_note1 = producer.insert(producer_note1)
		producer_note2 = frappe._dict(doctype='Note', title='test multiple doc sync 2')
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note2['title']})
		frappe.db.delete('Note', {'title': producer_note2['title']})
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
		producer = get_remote_site()
		producer_user = frappe._dict(doctype='User', email='test_user@sync.com', send_welcome_email=0,
			first_name='Test Sync User', enabled=1, roles=[{'role': 'System Manager'}])
		delete_on_remote_if_exists(producer, 'User', {'email': producer_user.email})
		frappe.db.delete('User', {'email':producer_user.email})
		producer_user = producer.insert(producer_user)

		producer_note = frappe._dict(doctype='Note', title='test child table dependency sync',
			seen_by=[{'user': producer_user.name}])
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note.title})
		frappe.db.delete('Note', {'title': producer_note.title})
		producer_note = producer.insert(producer_note)

		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('User', producer_user.name))
		if self.assertTrue(frappe.db.exists('Note', producer_note.name)):
			local_note = frappe.get_doc('Note', producer_note.name)
			self.assertEqual(len(local_note.seen_by), 1)

	def test_dynamic_link_dependencies_synced(self):
		producer = get_remote_site()
		#unsubscribe for Note to check whether dependency is fulfilled
		event_producer = frappe.get_doc('Event Producer', producer_url)
		event_producer.producer_doctypes = []
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 1
		})
		event_producer.save()

		producer_link_doc = frappe._dict(doctype='Note', title='Test Dynamic Link 1')

		delete_on_remote_if_exists(producer, 'Note', {'title': producer_link_doc.title})
		frappe.db.delete('Note', {'title': producer_link_doc.title})
		producer_link_doc = producer.insert(producer_link_doc)
		producer_doc = frappe._dict(doctype='ToDo', description='Test Dynamic Link 2', assigned_by='Administrator',
				reference_type='Note', reference_name=producer_link_doc.name)
		producer_doc = producer.insert(producer_doc)

		self.pull_producer_data()

		#check dynamic link dependency created
		self.assertTrue(frappe.db.exists('Note', producer_link_doc.name))
		self.assertEqual(producer_link_doc.name, frappe.db.get_value('ToDo', producer_doc.name, 'reference_name'))

		reset_configuration(producer_url)

	def test_naming_configuration(self):
		#test with use_same_name = 0
		producer = get_remote_site()
		event_producer = frappe.get_doc('Event Producer', producer_url)
		event_producer.producer_doctypes = []
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 0
		})
		event_producer.save()

		producer_doc = insert_into_producer(producer, 'test different name sync')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('ToDo', {'remote_docname': producer_doc.name, 'remote_site_name': producer_url}))

		reset_configuration(producer_url)

	def test_update_log(self):
		producer = get_remote_site()
		producer_doc = insert_into_producer(producer, 'test update log')
		update_log_doc = producer.get_value('Event Update Log', 'docname', {'docname': producer_doc.get('name')})
		self.assertEqual(update_log_doc.get('docname'), producer_doc.get('name'))

	def test_event_sync_log(self):
		producer = get_remote_site()
		producer_doc = insert_into_producer(producer, 'test event sync log')
		self.pull_producer_data()
		self.assertTrue(frappe.db.exists('Event Sync Log', {'docname': producer_doc.name}))

	def pull_producer_data(self):
		pull_from_node(producer_url)

	def get_remote_site(self):
		producer_doc = frappe.get_doc('Event Producer', producer_url)
		producer_site = FrappeClient(
			url=producer_doc.producer_url,
			api_key=producer_doc.api_key,
			api_secret=producer_doc.get_password('api_secret'),
			frappe_authorization_source='Event Consumer'
		)
		return producer_site

	def test_mapping(self):
		producer = get_remote_site()
		event_producer = frappe.get_doc('Event Producer', producer_url)
		event_producer.producer_doctypes = []
		mapping = [{
			'local_fieldname': 'description',
			'remote_fieldname': 'content'
		}]
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 1,
			'has_mapping': 1,
			'mapping': get_mapping('ToDo to Note', 'ToDo', 'Note', mapping)
		})
		event_producer.save()

		producer_note = frappe._dict(doctype='Note', title='Test Mapping', content='Test Mapping')
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note.title})
		producer_note = producer.insert(producer_note)
		self.pull_producer_data()
		#check inserted
		self.assertTrue(frappe.db.exists('ToDo', {'description': producer_note.content}))

		#update in producer
		producer_note['content'] = 'test mapped doc update sync'
		producer_note = producer.update(producer_note)
		self.pull_producer_data()

		# check updated
		self.assertTrue(frappe.db.exists('ToDo', {'description': producer_note['content']}))

		producer.delete('Note', producer_note.name)
		self.pull_producer_data()
		#check delete
		self.assertFalse(frappe.db.exists('ToDo', {'description': producer_note.content}))

		reset_configuration(producer_url)

	def test_inner_mapping(self):
		producer = get_remote_site()
		event_producer = frappe.get_doc('Event Producer', producer_url)
		event_producer.producer_doctypes = []
		inner_mapping = [
			{
				'local_fieldname':'role_name',
				'remote_fieldname':'title'
			}
		]
		inner_map = get_mapping('Role to Note Dependency Creation', 'Role', 'Note', inner_mapping)
		mapping = [
			{
				'local_fieldname':'description',
				'remote_fieldname':'content',
			},
			{
				'local_fieldname': 'role',
				'remote_fieldname': 'title',
				'mapping_type': 'Document',
				'mapping': inner_map,
				'remote_value_filters': json.dumps({'title': 'title'})
			}
		]
		event_producer.append('producer_doctypes', {
			'ref_doctype': 'ToDo',
			'use_same_name': 1,
			'has_mapping': 1,
			'mapping': get_mapping('ToDo to Note Mapping', 'ToDo', 'Note', mapping)
		})
		event_producer.save()

		producer_note = frappe._dict(doctype='Note', title='Inner Mapping Tester', content='Test Inner Mapping')
		delete_on_remote_if_exists(producer, 'Note', {'title': producer_note.title})
		producer_note = producer.insert(producer_note)
		self.pull_producer_data()

		#check dependency inserted
		self.assertTrue(frappe.db.exists('Role', {'role_name': producer_note.title}))
		#check doc inserted
		self.assertTrue(frappe.db.exists('ToDo', {'description': producer_note.content}))

		reset_configuration(producer_url)


def insert_into_producer(producer, description):
	#create and insert todo on remote site
	todo = dict(doctype='ToDo', description=description, assigned_by='Administrator')
	return producer.insert(todo)

def delete_on_remote_if_exists(producer, doctype, filters):
	remote_doc = producer.get_value(doctype, 'name', filters)
	if remote_doc:
		producer.delete(doctype, remote_doc.get('name'))

def get_mapping(mapping_name, local, remote, field_map):
	name = frappe.db.exists('Document Type Mapping', mapping_name)
	if name:
		doc = frappe.get_doc('Document Type Mapping', name)
	else:
		doc = frappe.new_doc('Document Type Mapping')

	doc.mapping_name = mapping_name
	doc.local_doctype = local
	doc.remote_doctype = remote
	for entry in field_map:
		doc.append('field_mapping', entry)
	doc.save()
	return doc.name


def create_event_producer(producer_url):
	if frappe.db.exists('Event Producer', producer_url):
		return
	event_producer = frappe.new_doc('Event Producer')
	event_producer.producer_doctypes = []
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
	event_producer.save()

def reset_configuration(producer_url):
	event_producer = frappe.get_doc('Event Producer', producer_url)
	event_producer.producer_doctypes = []
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
	event_producer.save()

def get_remote_site():
	producer_doc = frappe.get_doc('Event Producer', producer_url)
	producer_site = FrappeClient(
		url=producer_doc.producer_url,
		api_key=producer_doc.api_key,
		api_secret=producer_doc.get_password('api_secret'),
		frappe_authorization_source='Event Consumer'
	)
	return producer_site
