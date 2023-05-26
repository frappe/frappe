import unittest
from collections.abc import Callable
from datetime import time

import frappe
from frappe.query_builder import Case
from frappe.query_builder.builder import Function
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import (
	Cast_,
	Coalesce,
	CombineDatetime,
	Date,
	GroupConcat,
	Match,
	Round,
	Truncate,
	UnixTimestamp,
)
from frappe.query_builder.utils import db_type_is
from frappe.tests.utils import FrappeTestCase


def run_only_if(dbtype: db_type_is) -> Callable:
	return unittest.skipIf(db_type_is(frappe.conf.db_type) != dbtype, f"Only runs for {dbtype.value}")


@run_only_if(db_type_is.MARIADB)
class TestCustomFunctionsMariaDB(FrappeTestCase):
	def test_concat(self):
		self.assertEqual("GROUP_CONCAT('Notes')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes")
		with self.assertRaises(Exception):
			query.get_sql()
		query = query.Against("text")
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

	def test_unix_ts_mariadb(self):
		# Simple Query
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"unix_timestamp(posting_date)",
			UnixTimestamp(note.posting_date).get_sql(),
		)

		# Complex multi table query
		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(UnixTimestamp(note.posting_date))
		)
		self.assertIn("select unix_timestamp(`tabnote`.`posting_date`)", str(select_query).lower())

		# Order by
		select_query = select_query.orderby(UnixTimestamp(note.posting_date))
		self.assertIn(
			"order by unix_timestamp(`tabnote`.`posting_date`)",
			str(select_query).lower(),
		)

		# Function comparison
		select_query = select_query.where(
			UnixTimestamp(note.posting_date) >= UnixTimestamp("2021-01-01")
		)
		self.assertIn(
			"unix_timestamp(`tabnote`.`posting_date`)>=unix_timestamp('2021-01-01')",
			str(select_query).lower(),
		)

		# aliasing
		select_query = select_query.select(UnixTimestamp(note.posting_date, alias="unix_ts"))
		self.assertIn(
			"unix_timestamp(`tabnote`.`posting_date`) `unix_ts`",
			str(select_query).lower(),
		)

	def test_time(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"TIMESTAMP('2021-01-01','00:00:21')", CombineDatetime("2021-01-01", time(0, 0, 21)).get_sql()
		)

		select_query = frappe.qb.from_(note).select(
			CombineDatetime(note.posting_date, note.posting_time)
		)
		self.assertIn("select timestamp(`posting_date`,`posting_time`)", str(select_query).lower())

		select_query = select_query.where(
			CombineDatetime(note.posting_date, note.posting_time)
			>= CombineDatetime("2021-01-01", time(0, 0, 1))
		)
		self.assertIn(
			"timestamp(`posting_date`,`posting_time`)>=timestamp('2021-01-01','00:00:01')",
			str(select_query).lower(),
		)

	def test_cast(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual("CONCAT(name,'')", Cast_(note.name, "varchar").get_sql())
		self.assertEqual("CAST(name AS INTEGER)", Cast_(note.name, "integer").get_sql())
		self.assertEqual(
			frappe.qb.from_("red").from_(note).select("other", Cast_(note.name, "varchar")).get_sql(),
			"SELECT `tabred`.`other`,CONCAT(`tabNote`.`name`,'') FROM `tabred`,`tabNote`",
		)

	def test_round(self):
		note = frappe.qb.DocType("Note")

		query = frappe.qb.from_(note).select(Round(note.price))
		self.assertEqual("select round(`price`,0) from `tabnote`", str(query).lower())

		query = frappe.qb.from_(note).select(Round(note.price, 3))
		self.assertEqual("select round(`price`,3) from `tabnote`", str(query).lower())

	def test_truncate(self):
		note = frappe.qb.DocType("Note")
		query = frappe.qb.from_(note).select(Truncate(note.price, 3))
		self.assertEqual("select truncate(`price`,3) from `tabnote`", str(query).lower())


@run_only_if(db_type_is.POSTGRES)
class TestCustomFunctionsPostgres(FrappeTestCase):
	def test_concat(self):
		self.assertEqual("STRING_AGG('Notes',',')", GroupConcat("Notes").get_sql())

	def test_match(self):
		query = Match("Notes")
		self.assertEqual("TO_TSVECTOR('Notes')", query.get_sql())
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

	def test_unix_ts_postgres(self):
		# Simple Query
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"extract(epoch from posting_date)",
			UnixTimestamp(note.posting_date).get_sql().lower(),
		)

		# Complex multi table query
		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(UnixTimestamp(note.posting_date))
		)
		self.assertIn('extract(epoch from "tabnote"."posting_date")', str(select_query).lower())

		# Order by
		select_query = select_query.orderby(UnixTimestamp(note.posting_date))
		self.assertIn(
			'order by extract(epoch from "tabnote"."posting_date")',
			str(select_query).lower(),
		)

		# Function comparison
		select_query = select_query.where(
			UnixTimestamp(note.posting_date) >= UnixTimestamp(Date("2021-01-01"))
		)
		self.assertIn(
			'extract(epoch from "tabnote"."posting_date")>=extract(epoch from date(\'2021-01-01\'))',
			str(select_query).lower(),
		)

		# aliasing
		select_query = select_query.select(UnixTimestamp(note.posting_date, alias="unix_ts"))
		self.assertIn(
			'extract(epoch from "tabnote"."posting_date") "unix_ts"',
			str(select_query).lower(),
		)

	def test_time(self):
		note = frappe.qb.DocType("Note")

		self.assertEqual(
			"CAST('2021-01-01' AS DATE)+CAST('00:00:21' AS TIME)",
			CombineDatetime("2021-01-01", time(0, 0, 21)).get_sql(),
		)

		select_query = frappe.qb.from_(note).select(
			CombineDatetime(note.posting_date, note.posting_time)
		)
		self.assertIn('select "posting_date"+"posting_time"', str(select_query).lower())

		select_query = select_query.where(
			CombineDatetime(note.posting_date, note.posting_time)
			>= CombineDatetime("2021-01-01", time(0, 0, 1))
		)
		self.assertIn(
			"""where "posting_date"+"posting_time">=cast('2021-01-01' as date)+cast('00:00:01' as time)""",
			str(select_query).lower(),
		)

	def test_cast(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual("CAST(name AS VARCHAR)", Cast_(note.name, "varchar").get_sql())
		self.assertEqual("CAST(name AS INTEGER)", Cast_(note.name, "integer").get_sql())
		self.assertEqual(
			frappe.qb.from_("red").from_(note).select("other", Cast_(note.name, "varchar")).get_sql(),
			'SELECT "tabred"."other",CAST("tabNote"."name" AS VARCHAR) FROM "tabred","tabNote"',
		)

	def test_round(self):
		note = frappe.qb.DocType("Note")

		query = frappe.qb.from_(note).select(Round(note.price))
		self.assertEqual('select round("price",0) from "tabnote"', str(query).lower())

		query = frappe.qb.from_(note).select(Round(note.price, 3))
		self.assertEqual('select round("price",3) from "tabnote"', str(query).lower())

	def test_truncate(self):
		note = frappe.qb.DocType("Note")
		query = frappe.qb.from_(note).select(Truncate(note.price, 3))
		self.assertEqual('select truncate("price",3) from "tabnote"', str(query).lower())


class TestBuilderBase:
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

	def test_agg_funcs(self):
		frappe.db.truncate("Communication")
		sample_data = {
			"doctype": "Communication",
			"communication_type": "Communication",
			"content": "testing",
			"rating": 1,
		}
		frappe.get_doc(sample_data).insert()
		sample_data["rating"] = 3
		frappe.get_doc(sample_data).insert()
		sample_data["rating"] = 4
		frappe.get_doc(sample_data).insert()
		self.assertEqual(frappe.qb.max("Communication", "rating"), 4)
		self.assertEqual(frappe.qb.min("Communication", "rating"), 1)
		self.assertAlmostEqual(frappe.qb.avg("Communication", "rating"), 2.666, places=2)
		self.assertEqual(frappe.qb.sum("Communication", "rating"), 8.0)
		frappe.db.rollback()


class TestParameterization(FrappeTestCase):
	def test_where_conditions(self):
		DocType = frappe.qb.DocType("DocType")
		query = frappe.qb.from_(DocType).select(DocType.name).where(DocType.owner == "Administrator' --")
		self.assertTrue("walk" in dir(query))
		query, params = query.walk()

		self.assertIn("%(param1)s", query)
		self.assertIn("param1", params)
		self.assertEqual(params["param1"], "Administrator' --")

	def test_set_conditions(self):
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

	def test_named_parameter_wrapper(self):
		from frappe.query_builder.terms import NamedParameterWrapper

		test_npw = NamedParameterWrapper()
		self.assertTrue(hasattr(test_npw, "parameters"))
		self.assertEqual(test_npw.get_sql("test_string_one"), "%(param1)s")
		self.assertEqual(test_npw.get_sql("test_string_two"), "%(param2)s")
		params = test_npw.get_parameters()
		for key in params.keys():
			# checks for param# format
			self.assertRegex(key, r"param\d")
		self.assertEqual(params["param1"], "test_string_one")


@run_only_if(db_type_is.MARIADB)
class TestBuilderMaria(FrappeTestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual("SELECT * FROM `tabNotes`", frappe.qb.from_("Notes").select("*").get_sql())
		self.assertEqual("SELECT * FROM `__Auth`", frappe.qb.from_("__Auth").select("*").get_sql())

	def test_get_qb_type(self):
		from frappe.query_builder import get_query_builder

		qb = get_query_builder(frappe.db.db_type)
		self.assertEqual("SELECT * FROM `tabDocType`", qb().from_("DocType").select("*").get_sql())


@run_only_if(db_type_is.POSTGRES)
class TestBuilderPostgres(FrappeTestCase, TestBuilderBase):
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

	def test_get_qb_type(self):
		from frappe.query_builder import get_query_builder

		qb = get_query_builder(frappe.db.db_type)
		self.assertEqual('SELECT * FROM "tabDocType"', qb().from_("DocType").select("*").get_sql())


class TestMisc(FrappeTestCase):
	def test_custom_func(self):
		rand_func = frappe.qb.functions("rand", "45")
		self.assertIsInstance(rand_func, Function)
		self.assertEqual(rand_func.get_sql(), "rand('45')")

	def test_function_with_schema(self):
		from frappe.query_builder import ParameterizedFunction

		x = ParameterizedFunction("rand", "45")
		x.schema = frappe.qb.DocType("DocType")
		self.assertEqual("tabDocType.rand('45')", x.get_sql())

	def test_util_table(self):
		from frappe.query_builder.utils import Table

		DocType = Table("DocType")
		self.assertEqual(DocType.get_sql(), "DocType")

	def test_error_on_query_class(self):
		import frappe.query_builder.utils

		frappe.query_builder.utils.get_type_hints = lambda x: {"return": None}

		with self.assertRaises(frappe.query_builder.utils.BuilderIdentificationFailed):
			frappe.query_builder.utils.patch_query_execute()
