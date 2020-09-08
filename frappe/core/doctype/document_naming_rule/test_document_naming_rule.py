# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestDocumentNamingRule(unittest.TestCase):
	def test_naming_rule_by_field(self):
		naming_rule = frappe.get_doc(dict(
			doctype = 'Document Naming Rule',
			document_type = 'ToDo',
			naming_by = 'Field Value',
			naming_field = 'description'
		)).insert()

		todo = frappe.get_doc(dict(
			doctype = 'ToDo',
			description = 'Is this my name ' + frappe.generate_hash()
		)).insert()

		self.assertEqual(todo.name, todo.description)

		naming_rule.delete()
		todo.delete()

	def test_naming_rule_by_series(self):
		naming_rule = frappe.get_doc(dict(
			doctype = 'Document Naming Rule',
			document_type = 'ToDo',
			naming_by = 'Numbered',
			prefix = 'test-todo-',
			prefix_digits = 5
		)).insert()

		todo = frappe.get_doc(dict(
			doctype = 'ToDo',
			description = 'Is this my name ' + frappe.generate_hash()
		)).insert()

		self.assertEqual(todo.name, 'test-todo-00001')

		naming_rule.delete()
		todo.delete()

	def test_naming_rule_by_condition(self):
		naming_rule = frappe.get_doc(dict(
			doctype = 'Document Naming Rule',
			document_type = 'ToDo',
			naming_by = 'Numbered',
			prefix = 'test-high-',
			prefix_digits = 5,
			conditions = [dict(
				field = 'priority',
				condition = '=',
				value = 'High'
			)]
		)).insert()

		naming_rule_1 = frappe.copy_doc(naming_rule)
		naming_rule_1.prefix = 'test-medium-'
		naming_rule_1.conditions[0].value = 'Medium'
		naming_rule_1.insert()

		todo = frappe.get_doc(dict(
			doctype = 'ToDo',
			priority = 'High',
			description = 'Is this my name ' + frappe.generate_hash()
		)).insert()

		todo_1 = frappe.get_doc(dict(
			doctype = 'ToDo',
			priority = 'Medium',
			description = 'Is this my name ' + frappe.generate_hash()
		)).insert()

		try:
			self.assertEqual(todo.name, 'test-high-00001')
			self.assertEqual(todo_1.name, 'test-medium-00001')
		finally:
			naming_rule.delete()
			naming_rule_1.delete()
			todo.delete()
			todo_1.delete()
