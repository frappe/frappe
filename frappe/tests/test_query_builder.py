import unittest
from typing import Callable

import frappe
from frappe.query_builder import Case
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import Coalesce, CombineDatetime, GroupConcat, Match
from frappe.query_builder.utils import db_type_is


def run_only_if(dbtype: db_type_is) -> Callable:
	return unittest.skipIf(db_type_is(frappe.conf.db_type) != dbtype, f"Only runs for {dbtype.value}")


@run_only_if(db_type_is.MARIADB)
class TestCustomFunctionsMariaDB(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("GROUP_CONCAT('Notes')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual(" MATCH('Notes') AGAINST ('+text*' IN BOOLEAN MODE)", query.get_sql())

	def test_constant_column(self):
		query = frappe.qb.from_("DocType").select("name", ConstantColumn("John").as_("User"))
		self.assertEqual(query.get_sql(), "SELECT `name`,'John' `User` FROM `tabDocType`")

	def test_timestamp(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"TIMESTAMP(posting_date,posting_time)",
			CombineDatetime(note.posting_date, note.posting_time).get_sql(),
		)
		self.assertEqual(
			"TIMESTAMP('2021-01-01','00:00:21')", CombineDatetime("2021-01-01", "00:00:21").get_sql()
		)

		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(CombineDatetime(note.posting_date, note.posting_time))
		)
		self.assertIn(
			"select timestamp(`tabnote`.`posting_date`,`tabnote`.`posting_time`)", str(select_query).lower()
		)

		select_query = select_query.orderby(CombineDatetime(note.posting_date, note.posting_time))
		self.assertIn(
			"order by timestamp(`tabnote`.`posting_date`,`tabnote`.`posting_time`)",
			str(select_query).lower(),
		)

		select_query = select_query.where(
			CombineDatetime(note.posting_date, note.posting_time)
			>= CombineDatetime("2021-01-01", "00:00:01")
		)
		self.assertIn(
			"timestamp(`tabnote`.`posting_date`,`tabnote`.`posting_time`)>=timestamp('2021-01-01','00:00:01')",
			str(select_query).lower(),
		)

		select_query = select_query.select(
			CombineDatetime(note.posting_date, note.posting_time, alias="timestamp")
		)
		self.assertIn(
			"timestamp(`tabnote`.`posting_date`,`tabnote`.`posting_time`) `timestamp`",
			str(select_query).lower(),
		)


@run_only_if(db_type_is.POSTGRES)
class TestCustomFunctionsPostgres(unittest.TestCase):
	def test_concat(self):
		self.assertEqual("STRING_AGG('Notes',',')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes").Against("text")
		self.assertEqual("TO_TSVECTOR('Notes') @@ PLAINTO_TSQUERY('text')", query.get_sql())

	def test_constant_column(self):
		query = frappe.qb.from_("DocType").select("name", ConstantColumn("John").as_("User"))
		self.assertEqual(query.get_sql(), 'SELECT "name",\'John\' "User" FROM "tabDocType"')

	def test_timestamp(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"posting_date+posting_time", CombineDatetime(note.posting_date, note.posting_time).get_sql()
		)
		self.assertEqual(
			"CAST('2021-01-01' AS DATE)+CAST('00:00:21' AS TIME)",
			CombineDatetime("2021-01-01", "00:00:21").get_sql(),
		)

		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(CombineDatetime(note.posting_date, note.posting_time))
		)
		self.assertIn(
			'select "tabnote"."posting_date"+"tabnote"."posting_time"', str(select_query).lower()
		)

		select_query = select_query.orderby(CombineDatetime(note.posting_date, note.posting_time))
		self.assertIn(
			'order by "tabnote"."posting_date"+"tabnote"."posting_time"', str(select_query).lower()
		)

		select_query = select_query.where(
			CombineDatetime(note.posting_date, note.posting_time)
			>= CombineDatetime("2021-01-01", "00:00:01")
		)
		self.assertIn(
			"""where "tabnote"."posting_date"+"tabnote"."posting_time">=cast('2021-01-01' as date)+cast('00:00:01' as time)""",
			str(select_query).lower(),
		)

		select_query = select_query.select(
			CombineDatetime(note.posting_date, note.posting_time, alias="timestamp")
		)
		self.assertIn(
			'"tabnote"."posting_date"+"tabnote"."posting_time" "timestamp"', str(select_query).lower()
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


class TestParameterization(unittest.TestCase):
	def test_where_conditions(self):
		DocType = frappe.qb.DocType("DocType")
		query = (
			frappe.qb.from_(DocType).select(DocType.name).where((DocType.owner == "Administrator' --"))
		)
		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "Administrator' --")

	def test_set_cnoditions(self):
		DocType = frappe.qb.DocType("DocType")
		query = frappe.qb.update(DocType).set(DocType.value, "some_value")

		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "some_value")

	def test_where_conditions_functions(self):
		DocType = frappe.qb.DocType("DocType")
		query = (
			frappe.qb.from_(DocType)
			.select(DocType.name)
			.where(Coalesce(DocType.search_fields == "subject"))
		)

		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "subject")

	def test_case(self):
		DocType = frappe.qb.DocType("DocType")
		query = frappe.qb.from_(DocType).select(
			Case()
			.when(DocType.search_fields == "value", "other_value")
			.when(Coalesce(DocType.search_fields == "subject_in_function"), "true_value")
			.else_("Overdue")
		)

		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "value")
		self.assertEqual(params["param2"], "other_value")
		self.assertEqual(params["param3"], "subject_in_function")
		self.assertEqual(params["param4"], "true_value")
		self.assertEqual(params["param5"], "Overdue")

	def test_case_in_update(self):
		DocType = frappe.qb.DocType("DocType")
		query = frappe.qb.update(DocType).set(
			"parent",
			Case()
			.when(DocType.search_fields == "value", "other_value")
			.when(Coalesce(DocType.search_fields == "subject_in_function"), "true_value")
			.else_("Overdue"),
		)

		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "value")
		self.assertEqual(params["param2"], "other_value")
		self.assertEqual(params["param3"], "subject_in_function")
		self.assertEqual(params["param4"], "true_value")
		self.assertEqual(params["param5"], "Overdue")


@run_only_if(db_type_is.MARIADB)
class TestBuilderMaria(unittest.TestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual("SELECT * FROM `tabNotes`", frappe.qb.from_("Notes").select("*").get_sql())
		self.assertEqual("SELECT * FROM `__Auth`", frappe.qb.from_("__Auth").select("*").get_sql())


@run_only_if(db_type_is.POSTGRES)
class TestBuilderPostgres(unittest.TestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual('SELECT * FROM "tabNotes"', frappe.qb.from_("Notes").select("*").get_sql())
		self.assertEqual('SELECT * FROM "__Auth"', frappe.qb.from_("__Auth").select("*").get_sql())

	def test_replace_tables(self):
		info_schema = frappe.qb.Schema("information_schema")
		self.assertEqual(
			'SELECT * FROM "pg_stat_all_tables"',
			frappe.qb.from_(info_schema.tables).select("*").get_sql(),
		)

	def test_replace_fields_post(self):
		self.assertEqual("relname", frappe.qb.Field("table_name").get_sql())
