# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.desk.doctype.todo.todo import ToDo

class TestHooks(unittest.TestCase):
	def test_hooks(self):
		hooks = frappe.get_hooks()
		self.assertTrue(isinstance(hooks.get("app_name"), list))
		self.assertTrue(isinstance(hooks.get("doc_events"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue(isinstance(hooks.get("doc_events").get("*"), dict))
		self.assertTrue("frappe.desk.notifications.clear_doctype_notifications" in
			hooks.get("doc_events").get("*").get("on_update"))

	def test_override_doctype_class(self):
		# mock get_hooks
		original = frappe.get_hooks
		def get_hooks(hook=None, default=None, app_name=None):
			if hook == 'override_doctype_class':
				return {
					'ToDo': ['frappe.tests.test_hooks.CustomToDo']
				}
			return original(hook, default, app_name)
		frappe.get_hooks = get_hooks

		todo = frappe.get_doc(doctype='ToDo', description='asdf')
		self.assertTrue(isinstance(todo, CustomToDo))

		# restore
		frappe.get_hooks = original

class CustomToDo(ToDo):
	pass
