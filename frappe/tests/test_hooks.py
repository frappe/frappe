# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.desk.doctype.todo.todo import ToDo
from frappe.cache_manager import clear_controller_cache

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
		from frappe import hooks
		
		# Set hook
		hooks.override_doctype_class = {
			'ToDo': ['frappe.tests.test_hooks.CustomToDo']
		}
		
		# Clear cache
		frappe.cache().delete_value('app_hooks')
		clear_controller_cache('ToDo')

		todo = frappe.get_doc(doctype='ToDo', description='asdf')
		self.assertTrue(isinstance(todo, CustomToDo))


class CustomToDo(ToDo):
	pass
