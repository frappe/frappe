import unittest
from typing import Callable

import frappe
from frappe.query_builder.functions import GroupConcat, Match
from frappe.query_builder.utils import db_type_is


def run_only_if(dbtype: db_type_is) -> Callable:
	return unittest.skipIf(
		db_type_is(frappe.conf.db_type) != dbtype, f"Only runs for {dbtype.value}"
	)


@run_only_if(db_type_is.MARIADB)
class TestCustomFunctionsMariaDB(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("GROUP_CONCAT('Notes')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual(
			" MATCH('Notes') AGAINST ('+text*' IN BOOLEAN MODE)", query.get_sql()
		)


@run_only_if(db_type_is.POSTGRES)
class TestCustomFunctionsPostgres(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("STRING_AGG('Notes',',')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual(
			"TO_TSVECTOR('Notes') @@ PLAINTO_TSQUERY('text')", query.get_sql()
		)


class TestBuilderBase(object):
	def test_adding_tabs(self):
		self.assertEqual("tabNotes", frappe.qb.DocType("Notes").get_sql())
		self.assertEqual("__Auth", frappe.qb.DocType("__Auth").get_sql())
		self.assertEqual("Notes", frappe.qb.Table("Notes").get_sql())

	def test_run_patcher(self):
		query = frappe.qb.from_("ToDo").select("*").limit(1)
		data = query.run(as_dict=True)
		self.assertTrue("run" in dir(query))
		self.assertIsInstance(query.run, Callable)
		self.assertIsInstance(data, list)

@run_only_if(db_type_is.MARIADB)
class TestBuilderMaria(unittest.TestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual(
			"SELECT * FROM `tabNotes`", frappe.qb.from_("Notes").select("*").get_sql()
		)
		self.assertEqual(
			"SELECT * FROM `__Auth`", frappe.qb.from_("__Auth").select("*").get_sql()
		)


@run_only_if(db_type_is.POSTGRES)
class TestBuilderPostgres(unittest.TestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual(
			'SELECT * FROM "tabNotes"', frappe.qb.from_("Notes").select("*").get_sql()
		)
		self.assertEqual(
			'SELECT * FROM "__Auth"', frappe.qb.from_("__Auth").select("*").get_sql()
		)

	def test_replace_tables(self):
		info_schema = frappe.qb.Schema("information_schema")
		self.assertEqual(
			'SELECT * FROM "pg_stat_all_tables"',
			frappe.qb.from_(info_schema.tables).select("*").get_sql(),
		)

	def test_replace_fields_post(self):
		self.assertEqual("relname", frappe.qb.Field("table_name").get_sql())
