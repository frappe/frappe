# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import time
from frappe import _
from frappe.commands.site import new_site
from frappe.frappeclient import FrappeClient
from frappe.offline.doctype.node_configuration.node_configuration import pull_master_data, get_current_node

class TestNodeConfiguration(unittest.TestCase):
	def test_insert(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test creation 1 sync')
		pull_master_data()
		time.sleep(1)
		self.assertTrue(frappe.db.exists('ToDo', master_doc.name))
		
	def test_update(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test update 1')
		master_doc['description'] = 'test update 2'
		master_doc = master.update(master_doc)
		pull_master_data()
		time.sleep(1)
		local_doc = frappe.get_doc(master_doc.doctype, master_doc.name)
		self.assertEqual(local_doc.description, master_doc.description)

	def test_delete(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test delete sync')
		pull_master_data()
		time.sleep(1)
		self.assertTrue(frappe.db.exists('ToDo', master_doc.name))
		master.delete('ToDo', master_doc.name)
		pull_master_data()
		time.sleep(1)
		self.assertFalse(frappe.db.exists('ToDo', master_doc.name))

	def test_multiple_doctypes_sync(self):
		master = self.get_client()

		#insert todo and note in master
		master_todo = self.insert_into_master(master, 'test multiple doc sync')
		master_note1 = frappe.get_doc(dict(doctype='Note', title='test multiple doc sync 1'))
		master_note1 = master.insert(master_note1)
		master_note2 = frappe.get_doc(dict(doctype='Note', title='test multiple doc sync 2'))
		master_note2 = master.insert(master_note2)

		#update in master
		master_todo['description'] = 'test multiple doc update sync'
		master_todo = master.update(master_todo)
		master_note1['content'] = 'testing update sync'
		master_note1 = master.update(master_note1)

		master.delete('Note', master_note2.name)

		pull_master_data()
		time.sleep(1)

		#check inserted
		self.assertTrue(frappe.db.exists('ToDo', master_todo.name))

		#check update
		local_todo = frappe.get_doc('ToDo', master_todo.name)
		self.assertEqual(local_todo.description, master_todo.description)
		local_note1 = frappe.get_doc('Note', master_note1.name)
		self.assertEqual(local_note1.content, master_note1.content)

		#check delete
		self.assertFalse(frappe.db.exists('Note', master_note2.name))

	def test_child_table_dependencies_fulfilled(self):
		master = self.get_client()
		master_user = frappe.get_doc(dict(doctype='User', email='test_user@sync.com', first_name='Test Sync User'))
		email_account = make_email_account_in_master(master, _('_Test Sync Email Account 1'), _('test-password1@example.com'))
		master_user.user_emails = []
		master_user.append('user_emails', {
			'email_account': email_account.name
		})
		master_user = master.insert(master_user)
		pull_master_data()
		time.sleep(1)
		self.assertTrue(frappe.db.exists('Email Account', email_account.name))
		if self.assertTrue(frappe.db.exists('User', master_user.name)):
			local_user = frappe.get_doc('User', master_user.name)
			self.assertEqual(len(local_user.user_emails), 3)

	def test_child_table_sync(self):
		master = self.get_client()
		master_doc = frappe.get_doc(dict(doctype='Node Configuration', master_node='http://test-site:8004', follower_node='http://test-site:8004'))
		master_doc.following_doctypes = []
		master_doc.append('following_doctypes', {
			'ref_doctype': 'ToDo'
		})
		master_doc.append('following_doctypes', {
			'ref_doctype': 'Note'
		})
		master_doc = master.insert(master_doc)
		pull_master_data()
		time.sleep(1)
		local_doc = frappe.get_doc('Node Configuration', master_doc.name)
		self.assertEqual(len(local_doc.following_doctypes), 2)		

	def insert_into_master(self, master, description):
		#create and insert todo on remote site
		todo = frappe.get_doc(dict(doctype='ToDo', description=description, assigned_by='Administrator'))
		return master.insert(todo)

	def get_client(self):
		#connect to remote master
		return FrappeClient('http://test-site-2:8004', 'Administrator', 'root')

def make_email_account_in_master(master, name, email_id):
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
	return master.insert(doc)