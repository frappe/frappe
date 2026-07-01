import unittest
from collections.abc import Callable
from datetime import time

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database.operator_map import func_in
from frappe.query_builder import Case
from frappe.query_builder.builder import Function
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import (
	Cast_,
	Coalesce,
	CombineDatetime,
	CurDate,
	Date,
	DateDiff,
	GroupConcat,
	JSONContains,
	JSONExtract,
	JSONValue,
	Match,
	Month,
	Quarter,
	Round,
	Truncate,
	UnixTimestamp,
)
from frappe.query_builder.utils import db_type_is
from frappe.tests import IntegrationTestCase


def run_only_if(dbtype: db_type_is) -> Callable:
	return unittest.skipIf(db_type_is(frappe.conf.db_type) != dbtype, f"Only runs for {dbtype.value}")


def unimplemented_for(*dbtypes: db_type_is) -> Callable:
	current_db_type = db_type_is(frappe.conf.db_type)
	return unittest.skipIf(current_db_type in dbtypes, f"Not Implemented for {current_db_type.value}")


@run_only_if(db_type_is.MARIADB)
class TestCustomFunctionsMariaDB(IntegrationTestCase):
	def test_concat(self):
		self.assertEqual("GROUP_CONCAT('Notes' SEPARATOR ',')", GroupConcat("Notes").get_sql())
		self.assertEqual("GROUP_CONCAT('Notes' SEPARATOR ', ')", GroupConcat("Notes", ", ").get_sql())
		user = frappe.qb.DocType("User")
		query = frappe.qb.from_(user).select(GroupConcat(user.email).separator(" | ").as_("user_list"))
		sql = query.get_sql()
		self.assertIn("SEPARATOR ' | '", sql)
		self.assertIn("`user_list`", sql)

	def test_like_keeps_native_operator(self):
		# MariaDB LIKE is already case-insensitive; keep the native operator
		user = frappe.qb.DocType("User")
		sql = frappe.qb.from_(user).select(user.name).where(user.name.like("%admin%")).get_sql()
		self.assertIn("LIKE", sql)
		self.assertNotIn("ILIKE", sql)
		not_sql = frappe.qb.from_(user).select(user.name).where(user.name.not_like("%admin%")).get_sql()
		self.assertIn("NOT LIKE", not_sql)

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
			CombineDatetime(note.posting_date, note.posting_time) >= CombineDatetime("2021-01-01", "00:00:01")
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

	def test_curdate(self):
		# CURRENT_DATE must render as a bare keyword (no parentheses) so it is valid on postgres too.
		self.assertEqual("CURRENT_DATE", CurDate().get_sql())
		note = frappe.qb.DocType("Note")
		query = frappe.qb.from_(note).select(note.name).where(note.posting_date >= CurDate())
		self.assertIn("current_date", str(query).lower())
		self.assertNotIn("current_date(", str(query).lower())

	def test_month_quarter_mariadb(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual("MONTH(posting_date)", Month(note.posting_date).get_sql())
		self.assertEqual("QUARTER(posting_date)", Quarter(note.posting_date).get_sql())

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
		select_query = select_query.where(UnixTimestamp(note.posting_date) >= UnixTimestamp("2021-01-01"))
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

	def test_datediff_mariadb(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"DATEDIFF(posting_date,creation)",
			DateDiff(note.posting_date, note.creation).get_sql(),
		)

		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(DateDiff(note.posting_date, note.creation))
		)
		self.assertIn(
			"select datediff(`tabnote`.`posting_date`,`tabnote`.`creation`)",
			str(select_query).lower(),
		)

	def test_time(self):
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"TIMESTAMP('2021-01-01','00:00:21')", CombineDatetime("2021-01-01", time(0, 0, 21)).get_sql()
		)

		select_query = frappe.qb.from_(note).select(CombineDatetime(note.posting_date, note.posting_time))
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

	def test_json_extract(self):
		note = frappe.qb.DocType("Note")
		# Simple get_sql
		self.assertEqual("JSON_EXTRACT(content,'$.key')", JSONExtract(note.content, "$.key").get_sql())

		# In a SELECT query
		query = frappe.qb.from_(note).select(JSONExtract(note.content, "$.key"))
		self.assertIn("json_extract(`content`,'$.key')", str(query).lower())

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONExtract(note.content, "$.key") == "value")
		self.assertIn("json_extract(`content`,'$.key')='value'", str(query).lower())

	def test_json_value(self):
		note = frappe.qb.DocType("Note")
		# Simple get_sql
		self.assertEqual(
			"JSON_UNQUOTE(JSON_EXTRACT(content,'$.key'))", JSONValue(note.content, "$.key").get_sql()
		)

		# In a SELECT query
		query = frappe.qb.from_(note).select(JSONValue(note.content, "$.key"))
		self.assertIn("json_unquote(json_extract(`content`,'$.key'))", str(query).lower())

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONValue(note.content, "$.key") == "value")
		self.assertIn("json_unquote(json_extract(`content`,'$.key'))='value'", str(query).lower())

	def test_json_contains(self):
		note = frappe.qb.DocType("Note")
		# With a plain string candidate (auto-wrapped as JSON)
		self.assertEqual("JSON_CONTAINS(content,'\"value\"')", JSONContains(note.content, "value").get_sql())

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONContains(note.content, "admin"))
		self.assertIn("json_contains(`content`,'\"admin\"')", str(query).lower())


@run_only_if(db_type_is.POSTGRES)
class TestCustomFunctionsPostgres(IntegrationTestCase):
	def test_concat(self):
		self.assertEqual("STRING_AGG('Notes',',')", GroupConcat("Notes").get_sql())
		self.assertEqual("STRING_AGG('Notes',', ')", GroupConcat("Notes", ", ").get_sql())
		# .separator() chaining must work on postgres too (STRING_AGG has no native SEPARATOR keyword)
		self.assertEqual("STRING_AGG('Notes',' | ')", GroupConcat("Notes").separator(" | ").get_sql())

	def test_like_is_case_insensitive(self):
		# postgres LIKE is case-sensitive; render ILIKE so search matches MariaDB's case-insensitivity
		user = frappe.qb.DocType("User")
		self.assertIn(
			"ILIKE", frappe.qb.from_(user).select(user.name).where(user.name.like("%admin%")).get_sql()
		)
		self.assertIn(
			"NOT ILIKE",
			frappe.qb.from_(user).select(user.name).where(user.name.not_like("%admin%")).get_sql(),
		)

	def test_match(self):
		# 'english' regconfig is pinned so a GIN index over to_tsvector('english', col) can back it
		query = Match("Notes")
		self.assertEqual("TO_TSVECTOR('english','Notes')", query.get_sql())
		query = Match("Notes").Against("text")
		self.assertEqual(
			"TO_TSVECTOR('english','Notes') @@ PLAINTO_TSQUERY('english', 'text')", query.get_sql()
		)

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
		self.assertIn('select "tabnote"."posting_date"+"tabnote"."posting_time"', str(select_query).lower())

		select_query = select_query.orderby(CombineDatetime(note.posting_date, note.posting_time))
		self.assertIn('order by "tabnote"."posting_date"+"tabnote"."posting_time"', str(select_query).lower())

		select_query = select_query.where(
			CombineDatetime(note.posting_date, note.posting_time) >= CombineDatetime("2021-01-01", "00:00:01")
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

	def test_curdate(self):
		# CURRENT_DATE must render as a bare keyword (no parentheses); postgres rejects CURRENT_DATE().
		self.assertEqual("CURRENT_DATE", CurDate().get_sql())
		note = frappe.qb.DocType("Note")
		query = frappe.qb.from_(note).select(note.name).where(note.posting_date >= CurDate())
		self.assertIn("current_date", str(query).lower())
		self.assertNotIn("current_date(", str(query).lower())

	def test_month_quarter_postgres(self):
		# date_part(...) is double precision on postgres; it is wrapped in CAST(... AS INTEGER) so
		# MONTH/QUARTER match MySQL's integer result (no `2.0` leaking into report output).
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"cast(date_part('month',posting_date) as integer)",
			Month(note.posting_date).get_sql().lower(),
		)
		self.assertEqual(
			"cast(date_part('quarter',posting_date) as integer)",
			Quarter(note.posting_date).get_sql().lower(),
		)
		# round-trips to a python int, like MariaDB's MONTH()/QUARTER()
		val = frappe.db.sql(
			f"SELECT {Month(CurDate()).get_sql()} AS m, {Quarter(CurDate()).get_sql()} AS q",
			as_dict=True,
		)[0]
		self.assertIsInstance(val["m"], int)
		self.assertIsInstance(val["q"], int)

	def test_unix_ts_postgres(self):
		# Simple Query
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"cast(extract(epoch from (cast(posting_date as timestamp) "
			"at time zone current_setting('timezone'))) as bigint)",
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
		self.assertIn(
			'cast(extract(epoch from (cast("tabnote"."posting_date" as timestamp) '
			"at time zone current_setting('timezone'))) as bigint)",
			str(select_query).lower(),
		)

	def test_unix_ts_postgres_uses_session_timezone(self):
		from datetime import datetime
		from zoneinfo import ZoneInfo

		dt = frappe.qb.DocType("DocType")
		epoch = UnixTimestamp(Date("2021-06-01"))
		try:
			for tz in ("UTC", "Asia/Kolkata", "America/New_York"):
				frappe.db.sql("SET LOCAL TIME ZONE %s", (tz,))
				got = frappe.qb.from_(dt).select(epoch).limit(1).run()[0][0]
				expected = int(datetime(2021, 6, 1, tzinfo=ZoneInfo(tz)).timestamp())
				self.assertEqual(got, expected, msg=f"timezone {tz}")
		finally:
			frappe.db.sql("RESET TIME ZONE")

	def test_datediff_postgres(self):
		# Postgres subtracts dates to get an integer day count, matching MariaDB DATEDIFF.
		note = frappe.qb.DocType("Note")
		self.assertEqual(
			"posting_date-creation",
			DateDiff(note.posting_date, note.creation).get_sql(),
		)
		self.assertEqual(
			"CAST('2024-01-10' AS DATE)-creation",
			DateDiff("2024-01-10", note.creation).get_sql(),
		)

		todo = frappe.qb.DocType("ToDo")
		select_query = (
			frappe.qb.from_(note)
			.join(todo)
			.on(todo.refernce_name == note.name)
			.select(DateDiff(note.posting_date, note.creation))
		)
		self.assertIn('select "tabnote"."posting_date"-"tabnote"."creation"', str(select_query).lower())

		# Order by
		select_query = select_query.orderby(UnixTimestamp(note.posting_date))
		self.assertIn(
			'order by cast(extract(epoch from (cast("tabnote"."posting_date" as timestamp) '
			"at time zone current_setting('timezone'))) as bigint)",
			str(select_query).lower(),
		)

		# Function comparison
		select_query = select_query.where(
			UnixTimestamp(note.posting_date) >= UnixTimestamp(Date("2021-01-01"))
		)
		self.assertIn(
			'cast(extract(epoch from (cast("tabnote"."posting_date" as timestamp) '
			"at time zone current_setting('timezone'))) as bigint)"
			">=cast(extract(epoch from (cast(date('2021-01-01') as timestamp) "
			"at time zone current_setting('timezone'))) as bigint)",
			str(select_query).lower(),
		)

		# aliasing
		select_query = select_query.select(UnixTimestamp(note.posting_date, alias="unix_ts"))
		self.assertIn(
			'cast(extract(epoch from (cast("tabnote"."posting_date" as timestamp) '
			"at time zone current_setting('timezone'))) as bigint) \"unix_ts\"",
			str(select_query).lower(),
		)

	def test_time(self):
		note = frappe.qb.DocType("Note")

		self.assertEqual(
			"CAST('2021-01-01' AS DATE)+CAST('00:00:21' AS TIME)",
			CombineDatetime("2021-01-01", time(0, 0, 21)).get_sql(),
		)

		select_query = frappe.qb.from_(note).select(CombineDatetime(note.posting_date, note.posting_time))
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

	def test_json_extract(self):
		note = frappe.qb.DocType("Note")
		# Simple get_sql
		self.assertEqual("\"content\"->'$.key'", JSONExtract(note.content, "$.key").get_sql())

		# In a SELECT query
		query = frappe.qb.from_(note).select(JSONExtract(note.content, "$.key"))
		self.assertIn("\"content\"->'$.key'", str(query))

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONExtract(note.content, "$.key") == "value")
		self.assertIn("\"content\"->'$.key'='value'", str(query))

	def test_json_value(self):
		note = frappe.qb.DocType("Note")
		# Simple get_sql
		self.assertEqual("\"content\"->>'$.key'", JSONValue(note.content, "$.key").get_sql())

		# In a SELECT query
		query = frappe.qb.from_(note).select(JSONValue(note.content, "$.key"))
		self.assertIn("\"content\"->>'$.key'", str(query))

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONValue(note.content, "$.key") == "value")
		self.assertIn("\"content\"->>'$.key'='value'", str(query))

	def test_json_contains(self):
		note = frappe.qb.DocType("Note")
		# With a plain string candidate
		self.assertEqual("\"content\"@>'admin'", JSONContains(note.content, "admin").get_sql())

		# In a WHERE clause
		query = frappe.qb.from_(note).select(note.name).where(JSONContains(note.content, "admin"))
		self.assertIn("\"content\"@>'admin'", str(query))


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
		doc = new_doctype(
			fields=[
				{
					"fieldname": "number",
					"fieldtype": "Int",
					"label": "Number",
					"reqd": 1,  # mandatory
				},
			],
		)
		doc.insert()
		self.doctype_name = doc.name
		frappe.db.truncate(self.doctype_name)
		sample_data = {
			"doctype": self.doctype_name,
			"number": 1,
		}
		frappe.get_doc(sample_data).insert(ignore_mandatory=True)
		sample_data["number"] = 3
		frappe.get_doc(sample_data).insert(ignore_mandatory=True)
		sample_data["number"] = 4
		frappe.get_doc(sample_data).insert(ignore_mandatory=True)
		self.assertEqual(frappe.qb.max(self.doctype_name, "number"), 4)
		self.assertEqual(frappe.qb.min(self.doctype_name, "number"), 1)
		self.assertAlmostEqual(frappe.qb.avg(self.doctype_name, "number"), 2.666, places=2)
		self.assertEqual(frappe.qb.sum(self.doctype_name, "number"), 8.0)
		frappe.db.rollback()


class TestParameterization(IntegrationTestCase):
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
			frappe.qb.from_(DocType).select(DocType.name).where(Coalesce(DocType.search_fields == "subject"))
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
class TestBuilderMaria(IntegrationTestCase, TestBuilderBase):
	def test_adding_tabs_in_from(self):
		self.assertEqual("SELECT * FROM `tabNotes`", frappe.qb.from_("Notes").select("*").get_sql())
		self.assertEqual("SELECT * FROM `__Auth`", frappe.qb.from_("__Auth").select("*").get_sql())

	def test_get_qb_type(self):
		from frappe.query_builder import get_query_builder

		qb = get_query_builder(frappe.db.db_type)
		self.assertEqual("SELECT * FROM `tabDocType`", qb().from_("DocType").select("*").get_sql())


@run_only_if(db_type_is.POSTGRES)
class TestBuilderPostgres(IntegrationTestCase, TestBuilderBase):
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


class TestMisc(IntegrationTestCase):
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

	def test_union(self):
		user = frappe.qb.DocType("User")
		role = frappe.qb.DocType("Role")
		users = frappe.qb.from_(user).select(user.name)
		roles = frappe.qb.from_(role).select(role.name)

		self.assertEqual(set(users.run() + roles.run()), set((users + roles).run()))


class TestOperatorIn(IntegrationTestCase):
	def test_func_in_without_empty_values(self):
		note = frappe.qb.DocType("Note")
		query = func_in(note.name, ["n1", "n2", "n3"])
		sql_str = str(query).lower()

		self.assertIn("in", sql_str)
		self.assertNotIn("coalesce", sql_str)

	def test_func_in_with_none_converts_to_empty_string(self):
		note = frappe.qb.DocType("Note")
		query = func_in(note.name, [None, "user1"])
		sql_str = str(query).lower()

		self.assertNotIn("coalesce", sql_str)
		self.assertIn("is null", sql_str)
		self.assertIn("''", sql_str)

	def test_func_in_with_empty_string_uses_or_is_null(self):
		note = frappe.qb.DocType("Note")
		query = func_in(note.name, ["", "user1"])
		sql_str = str(query).lower()

		self.assertNotIn("coalesce", sql_str)
		self.assertIn("is null", sql_str)
		self.assertIn("''", sql_str)

	def test_func_in_with_mixed_none_and_values(self):
		note = frappe.qb.DocType("Note")
		query = func_in(note.name, ["val1", None, "val2"])
		sql_str = str(query).lower()

		self.assertNotIn("coalesce", sql_str)
		self.assertIn("is null", sql_str)

	def test_in_filter_matches_null_and_empty_columns(self):
		test_doctype = new_doctype(
			fields=[
				{
					"fieldname": "test_field",
					"fieldtype": "Data",
					"label": "Test Field",
				},
			],
		)
		test_doctype.insert()
		self.test_doctype_name = test_doctype.name
		self.addCleanup(frappe.delete_doc, "DocType", self.test_doctype_name)

		doc_null = frappe.get_doc({"doctype": self.test_doctype_name, "test_field": None})
		doc_null.insert()
		doc_empty = frappe.get_doc({"doctype": self.test_doctype_name, "test_field": ""})
		doc_empty.insert()
		doc_user = frappe.get_doc({"doctype": self.test_doctype_name, "test_field": "user1"})
		doc_user.insert()

		results = frappe.get_all(
			self.test_doctype_name,
			filters={"test_field": ["in", [None, "user1"]]},
			pluck="test_field",
		)

		self.assertIn(None, results)
		self.assertIn("", results)
		self.assertIn("user1", results)


class TestRecursiveCTE(IntegrationTestCase):
	def test_recursive_keyword_is_emitted(self):
		# recursive=True renders WITH RECURSIVE so a CTE may reference itself in its recursive term.
		from pypika import AliasedQuery, Table

		nodes = Table("nodes")
		tree = AliasedQuery("tree")
		seed = frappe.qb.from_(nodes).select(nodes.name, nodes.parent).where(nodes.parent.isnull())
		recurse = (
			frappe.qb.from_(nodes).join(tree).on(nodes.parent == tree.name).select(nodes.name, nodes.parent)
		)
		query = frappe.qb.with_(seed + recurse, "tree", recursive=True).from_(tree).select(tree.name)
		self.assertIn("WITH RECURSIVE tree AS", query.get_sql())

	def test_non_recursive_with_matches_pypika(self):
		# recursive defaults to False and must keep pypika's exact multi-CTE formatting (the join
		# is ") ," between clauses) -- the override changes nothing on the non-recursive path.
		from pypika import AliasedQuery, Table

		a = frappe.qb.from_(Table("t1")).select("x")
		b = frappe.qb.from_(Table("t2")).select("y")
		sql = frappe.qb.with_(a, "cte_a").with_(b, "cte_b").from_(AliasedQuery("cte_a")).select("x").get_sql()
		self.assertTrue(sql.startswith("WITH cte_a AS "))
		self.assertNotIn("WITH RECURSIVE", sql)
		self.assertIn(") ,cte_b AS (", sql)
