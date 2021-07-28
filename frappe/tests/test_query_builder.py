import unittest
from typing import Callable

import frappe
from frappe.query_builder.functions import GroupConcat, Match
from frappe.query_builder.utils import db_type


def CheckDB(dbtype: db_type) -> Callable:
	return unittest.skipIf(
		db_type(frappe.conf.db_type) != dbtype, f"Only runs for{db_type}"
	)

@CheckDB(dbtype=db_type.MARIADB)
class TestCustomFunctionsMariaDB(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("GROUP_CONCAT('Notes')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual(
			" MATCH('Notes') AGAINST ('+text*' IN BOOLEAN MODE)", query.get_sql()
		)


@CheckDB(dbtype=db_type.POSTGRES)
class TestCustomFunctionsPostgres(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("STRING_AGG('Notes',',')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual(
			"TO_TSVECTOR('Notes') @@ PLAINTO_TSQUERY('text')", query.get_sql()
		)
