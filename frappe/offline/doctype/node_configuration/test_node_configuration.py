# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import time
from frappe.commands.site import new_site
from frappe.frappeclient import FrappeClient
from frappe.offline.doctype.node_configuration.node_configuration import pull_master_data, get_current_node

class TestNodeConfiguration(unittest.TestCase):
	def test_insert(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test creation 1 sync')
		pull_master_data()
		local_doc = frappe.get_doc(master_doc.doctype, master_doc.name)
		self.assertNotEqual(local_doc, [])
		
	def test_update(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test update 1')
		master_doc['description'] = 'test update 2'
		master_doc = master.update(master_doc)
		time.sleep(1)
		local_doc = frappe.get_doc(master_doc.doctype, master_doc.name)
		self.assertEqual(local_doc.description, master_doc.description)

	def test_delete(self):
		master = self.get_client()
		master_doc = self.insert_into_master(master, 'test delete sync')
		local_doc = frappe.get_doc(master_doc.doctype, master_doc.name)
		self.assertNotEqual(local_doc, [])
		master.delete('ToDo', master_doc.get('name'))
		pull_master_data()
		self.assertFalse(frappe.db.exists('ToDo', local_doc[0].name))
		
	def insert_into_master(self, master, description):
		#create and insert todo on remote site
		todo = frappe.get_doc(dict(doctype='ToDo', description=description, assigned_by='Administrator'))
		return master.insert(todo)

	def get_client(self):
		#connect to remote master
		return FrappeClient('http://test-site-2:8004', 'Administrator', 'root')
