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

	def test_set_value(self):
		todo1 = frappe.get_doc(dict(doctype='ToDo', description = 'test_set_value 1')).insert()
		todo2 = frappe.get_doc(dict(doctype='ToDo', description = 'test_set_value 2')).insert()

		frappe.db.set_value('ToDo', todo1.name, 'description', 'test_set_value change 1')
		self.assertEqual(frappe.db.get_value('ToDo', todo1.name, 'description'), 'test_set_value change 1')

		# multiple set-value
		frappe.db.set_value('ToDo', dict(description=('like', '%test_set_value%')),
			'description', 'change 2')

		self.assertEqual(frappe.db.get_value('ToDo', todo1.name, 'description'), 'change 2')
		self.assertEqual(frappe.db.get_value('ToDo', todo2.name, 'description'), 'change 2')


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


	def test_db_keywords_as_fields(self):
		"""Tests if DB keywords work as docfield names. If they're wrapped with grave accents."""
		# Using random.choices, picked out a list of 40 keywords for testing
		all_keywords = {
			"mariadb": ["CHARACTER", "DELAYED", "LINES", "EXISTS", "YEAR_MONTH", "LOCALTIME", "BOTH", "MEDIUMINT", "LEFT", "BINARY", "LEFT", "DEFAULT", "KILL", "WRITE", "SQL_SMALL_RESULT", "CURRENT_TIME", "CROSS", "SET", "TABLE", "ALTER", "CURRENT_TIMESTAMP", "XOR", "CASE", "ALL", "WHERE", "INT", "TO", "SOME", "DAY_MINUTE", "ALL", "ERRORS", "OPTIMIZE", "LOCK", "REPLACE", "HIGH_PRIORITY", "VARBINARY", "HELP", "IS", "CHAR", "DESCRIBE"],
			"postgres": ["WORK", "LANCOMPILER", "REAL", "HAVING", "REPEATABLE", "DATA", "USING", "BIT", "DEALLOCATE", "SERIALIZABLE", "CURSOR", "INHERITS", "ARRAY", "TRUE", "IGNORE", "PARAMETER_MODE", "ROW", "CHECKPOINT", "SHOW", "BY", "SIZE", "SCALE", "UNENCRYPTED", "WITH", "AND", "CONVERT", "FIRST", "SCOPE", "WRITE", "INTERVAL", "CHARACTER_SET_SCHEMA", "ADD", "LANCOMPILER", "SCROLL", "PRECISION", "NULL", "WHEN", "TRANSACTION_ACTIVE", "INT", "FORTRAN"]
		}
		fields = all_keywords[frappe.conf.db_type]
		test_doctype = "Keywords Test"

		frappe.get_doc({
			"doctype": "DocType",
			"name": test_doctype,
			"module": "Custom",
			"custom": 1,
			"fields": [{
				"label": field.title(),
				"fieldname": field.lower(),
				"fieldtype": "Data"
			} for field in fields]
		}).insert()

		frappe.delete_doc("DocType", test_doctype)

