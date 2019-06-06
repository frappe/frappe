#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

class TestDB(unittest.TestCase):
	def test_get_value(self):
		self.assertEqual(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertNotEquals(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Guest")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<", "B"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<=", "Administrator"]}), "Administrator")

		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name > 's' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">", "s"]}))

		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name >= 't' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">=", "t"]}))

	def test_escape(self):
		frappe.db.escape("香港濟生堂製藥有限公司 - IT".encode("utf-8"))

	def test_get_single_value(self):
		frappe.db.set_value('System Settings', 'System Settings', 'backup_limit', 5)
		frappe.db.commit()

		limit = frappe.db.get_single_value('System Settings', 'backup_limit')
		self.assertEqual(limit, 5)

	def test_log_touched_tables(self):
		frappe.flags.in_migrate = True
		frappe.flags.touched_tables = set()
		frappe.db.set_value('System Settings', 'System Settings', 'backup_limit', 5)
		self.assertIn('tabSingles', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo = frappe.get_doc({'doctype': 'ToDo', 'description': 'Random Description'})
		todo.save()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo.description = "Another Description"
		todo.save()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		if frappe.db.db_type != "postgres":
			frappe.flags.touched_tables = set()
			frappe.db.sql("UPDATE tabToDo SET description = 'Updated Description'")
			self.assertNotIn('tabToDo SET', frappe.flags.touched_tables)
			self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		todo.delete()
		self.assertIn('tabToDo', frappe.flags.touched_tables)

		frappe.flags.touched_tables = set()
		create_custom_field('ToDo', {'label': 'ToDo Custom Field'})

		self.assertIn('tabToDo', frappe.flags.touched_tables)
		self.assertIn('tabCustom Field', frappe.flags.touched_tables)
		frappe.flags.in_migrate = False
		frappe.flags.touched_tables.clear()
