# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import unittest

import frappe

class TestNestedSet(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tree_doc = frappe.get_doc({
				'doctype': 'DocType',
				'name': 'TreeDoc',
				'module': 'Custom',
				'is_tree': 1,
			}).insert()

	@classmethod
	def tearDownClass(cls):
		cls.tree_doc.delete()

	def test_creation(self):
		# TODO: add tests
		pass
