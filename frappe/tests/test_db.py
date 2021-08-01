#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import unittest
from random import choice
import datetime

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import random_string
from frappe.utils.testutils import clear_custom_fields


class TestDB(unittest.TestCase):
	def test_get_value(self):
		self.assertEqual(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertNotEquals(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Guest")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<", "Adn"]}), "Administrator")
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
		#setup
		values_dict = {
			"Float": 1.5,
			"Int": 1,
			"Percent": 55.5,
			"Currency": 12.5,
			"Data": "Test",
			"Date": datetime.datetime.now().date(),
			"Datetime": datetime.datetime.now(),
			"Time": datetime.timedelta(hours=9, minutes=45, seconds=10)
		}
		test_inputs = [{
			"fieldtype": fieldtype,
			"value": value} for fieldtype, value in values_dict.items()]
		for fieldtype in values_dict.keys():
			create_custom_field("Print Settings", {
				"fieldname": f"test_{fieldtype.lower()}",
				"label": f"Test {fieldtype}",
				"fieldtype": fieldtype,
			})

		#test
		for inp in test_inputs:
			fieldname = f"test_{inp['fieldtype'].lower()}"
			frappe.db.set_value("Print Settings", "Print Settings", fieldname, inp["value"])
			self.assertEqual(frappe.db.get_single_value("Print Settings", fieldname), inp["value"])

		#teardown 
		clear_custom_fields("Print Settings")

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
			"mariadb": ["CHARACTER", "DELAYED", "LINES", "EXISTS", "YEAR_MONTH", "LOCALTIME", "BOTH", "MEDIUMINT",
			"LEFT", "BINARY", "DEFAULT", "KILL", "WRITE", "SQL_SMALL_RESULT", "CURRENT_TIME", "CROSS", "INHERITS",
			"SELECT", "TABLE", "ALTER", "CURRENT_TIMESTAMP", "XOR", "CASE", "ALL", "WHERE", "INT", "TO", "SOME",
			"DAY_MINUTE", "ERRORS", "OPTIMIZE", "REPLACE", "HIGH_PRIORITY", "VARBINARY", "HELP", "IS",
			"CHAR", "DESCRIBE", "KEY"],
			"postgres": ["WORK", "LANCOMPILER", "REAL", "HAVING", "REPEATABLE", "DATA", "USING", "BIT", "DEALLOCATE",
			"SERIALIZABLE", "CURSOR", "INHERITS", "ARRAY", "TRUE", "IGNORE", "PARAMETER_MODE", "ROW", "CHECKPOINT",
			"SHOW", "BY", "SIZE", "SCALE", "UNENCRYPTED", "WITH", "AND", "CONVERT", "FIRST", "SCOPE", "WRITE", "INTERVAL",
			"CHARACTER_SET_SCHEMA", "ADD", "SCROLL", "NULL", "WHEN", "TRANSACTION_ACTIVE",
			"INT", "FORTRAN", "STABLE"]
		}
		created_docs = []

		# edit by rushabh: added [:1]
		# don't run every keyword! - if one works, they all do
		fields = all_keywords[frappe.conf.db_type][:1]
		test_doctype = "ToDo"

		def add_custom_field(field):
			create_custom_field(test_doctype, {
				"fieldname": field.lower(),
				"label": field.title(),
				"fieldtype": 'Data',
			})

		# Create custom fields for test_doctype
		for field in fields:
			add_custom_field(field)

		# Create documents under that doctype and query them via ORM
		for _ in range(10):
			docfields = { key.lower(): random_string(10) for key in fields }
			doc = frappe.get_doc({"doctype": test_doctype, "description": random_string(20), **docfields})
			doc.insert()
			created_docs.append(doc.name)

		random_field = choice(fields).lower()
		random_doc = choice(created_docs)
		random_value = random_string(20)

		# Testing read
		self.assertEqual(list(frappe.get_all("ToDo", fields=[random_field], limit=1)[0])[0], random_field)
		self.assertEqual(list(frappe.get_all("ToDo", fields=[f"`{random_field}` as total"], limit=1)[0])[0], "total")

		# Testing read for distinct and sql functions
		self.assertEqual(list(
			frappe.get_all("ToDo",
				fields=[f"`{random_field}` as total"],
				distinct=True,
				limit=1,
			)[0]
		)[0], "total")
		self.assertEqual(list(
			frappe.get_all("ToDo",
			fields=[f"`{random_field}`"],
			distinct=True,
			limit=1,
			)[0]
		)[0], random_field)
		self.assertEqual(list(
			frappe.get_all("ToDo",
				fields=[f"count(`{random_field}`)"],
				limit=1
			)[0]
		)[0], "count" if frappe.conf.db_type == "postgres" else f"count(`{random_field}`)")

		# Testing update
		frappe.db.set_value(test_doctype, random_doc, random_field, random_value)
		self.assertEqual(frappe.db.get_value(test_doctype, random_doc, random_field), random_value)

		# Cleanup - delete records and remove custom fields
		for doc in created_docs:
			frappe.delete_doc(test_doctype, doc)
		clear_custom_fields(test_doctype)
