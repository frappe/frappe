# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import inspect
import unittest
from random import choice
from unittest.mock import patch

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.database import savepoint
from frappe.database.database import Database
from frappe.query_builder import Field
from frappe.query_builder.functions import Concat_ws
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils import add_days, now, random_string
from frappe.utils.testutils import clear_custom_fields


class TestDB(unittest.TestCase):
	def test_get_value(self):
		self.assertEqual(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertNotEqual(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Guest")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<", "Adn"]}), "Administrator")
		self.assertEqual(frappe.db.get_value("User", {"name": ["<=", "Administrator"]}), "Administrator")
		self.assertEqual(
			frappe.db.get_value("User", {}, ["Max(name)"], order_by=None),
			frappe.db.sql("SELECT Max(name) FROM tabUser")[0][0],
		)
		self.assertEqual(
			frappe.db.get_value("User", {}, "Min(name)", order_by=None),
			frappe.db.sql("SELECT Min(name) FROM tabUser")[0][0],
		)
		self.assertIn(
			"for update",
			frappe.db.get_value(
				"User", Field("name") == "Administrator", for_update=True, run=False
			).lower(),
		)
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.from_(user_doctype).select(user_doctype.name, user_doctype.email).run(),
			frappe.db.get_values(
				user_doctype,
				filters={},
				fieldname=[user_doctype.name, user_doctype.email],
				order_by=None,
			),
		)
		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name > 's' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">", "s"]}))

		self.assertEqual(frappe.db.sql("""SELECT name FROM `tabUser` WHERE name >= 't' ORDER BY MODIFIED DESC""")[0][0],
			frappe.db.get_value("User", {"name": [">=", "t"]}))
		self.assertEqual(
			frappe.db.get_values(
				"User",
				filters={"name": "Administrator"},
				distinct=True,
				fieldname="email",
			),
			frappe.qb.from_(user_doctype)
			.where(user_doctype.name == "Administrator")
			.select("email")
			.distinct()
			.run(),
		)

		self.assertIn(
			"concat_ws",
			frappe.db.get_value(
				"User",
				filters={"name": "Administrator"},
				fieldname=Concat_ws(" ", "LastName"),
				run=False,
			).lower(),
		)
		self.assertEqual(
			frappe.db.sql("select email from tabUser where name='Administrator' order by modified DESC"),
			frappe.db.get_values(
				"User", filters=[["name", "=", "Administrator"]], fieldname="email"
			),
		)

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
			docfields = {key.lower(): random_string(10) for key in fields}
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

	def test_savepoints(self):
		frappe.db.rollback()
		save_point = "todonope"

		created_docs = []
		failed_docs = []

		for _ in range(5):
			frappe.db.savepoint(save_point)
			doc_gone = frappe.get_doc(doctype="ToDo", description="nope").save()
			failed_docs.append(doc_gone.name)
			frappe.db.rollback(save_point=save_point)
			doc_kept = frappe.get_doc(doctype="ToDo", description="nope").save()
			created_docs.append(doc_kept.name)
		frappe.db.commit()

		for d in failed_docs:
			self.assertFalse(frappe.db.exists("ToDo", d))
		for d in created_docs:
			self.assertTrue(frappe.db.exists("ToDo", d))

	def test_savepoints_wrapper(self):
		frappe.db.rollback()

		class SpecificExc(Exception):
			pass

		created_docs = []
		failed_docs = []

		for _ in range(5):
			with savepoint(catch=SpecificExc):
				doc_kept = frappe.get_doc(doctype="ToDo", description="nope").save()
				created_docs.append(doc_kept.name)

			with savepoint(catch=SpecificExc):
				doc_gone = frappe.get_doc(doctype="ToDo", description="nope").save()
				failed_docs.append(doc_gone.name)
				raise SpecificExc

		frappe.db.commit()

		for d in failed_docs:
			self.assertFalse(frappe.db.exists("ToDo", d))
		for d in created_docs:
			self.assertTrue(frappe.db.exists("ToDo", d))

	def test_transaction_writes_error(self):
		from frappe.database.database import Database
		frappe.db.rollback()

		frappe.db.MAX_WRITES_PER_TRANSACTION = 1
		note = frappe.get_last_doc("ToDo")
		note.description = "changed"
		with self.assertRaises(frappe.TooManyWritesError) as tmw:
			note.save()

		frappe.db.MAX_WRITES_PER_TRANSACTION = Database.MAX_WRITES_PER_TRANSACTION

	def test_pk_collision_ignoring(self):
		# note has `name` generated from title
		for _ in range(3):
			frappe.get_doc(doctype="Note", title="duplicate name").insert(ignore_if_duplicate=True)

		with savepoint():
			self.assertRaises(frappe.DuplicateEntryError, frappe.get_doc(doctype="Note", title="duplicate name").insert)
			# recover transaction to continue other tests
			raise Exception


@run_only_if(db_type_is.MARIADB)
class TestDDLCommandsMaria(unittest.TestCase):
	test_table_name = "TestNotes"

	def setUp(self) -> None:
		frappe.db.commit()
		frappe.db.sql(
			f"""
			CREATE TABLE `tab{self.test_table_name}` (`id` INT NULL, content TEXT, PRIMARY KEY (`id`));
			"""
		)

	def tearDown(self) -> None:
		frappe.db.sql(f"DROP TABLE tab{self.test_table_name};")
		self.test_table_name = "TestNotes"

	def test_rename(self) -> None:
		new_table_name = f"{self.test_table_name}_new"
		frappe.db.rename_table(self.test_table_name, new_table_name)
		check_exists = frappe.db.sql(
			f"""
			SELECT * FROM INFORMATION_SCHEMA.TABLES
			WHERE TABLE_NAME = N'tab{new_table_name}';
			"""
		)
		self.assertGreater(len(check_exists), 0)
		self.assertIn(f"tab{new_table_name}", check_exists[0])

		# * so this table is deleted after the rename
		self.test_table_name = new_table_name

	def test_describe(self) -> None:
		self.assertEqual(
			(
				("id", "int(11)", "NO", "PRI", None, ""),
				("content", "text", "YES", "", None, ""),
			),
			frappe.db.describe(self.test_table_name),
		)

	def test_change_type(self) -> None:
		frappe.db.change_column_type("TestNotes", "id", "varchar(255)")
		test_table_description = frappe.db.sql(f"DESC tab{self.test_table_name};")
		self.assertGreater(len(test_table_description), 0)
		self.assertIn("varchar(255)", test_table_description[0])

	def test_add_index(self) -> None:
		index_name = "test_index"
		frappe.db.add_index(self.test_table_name, ["id", "content(50)"], index_name)
		indexs_in_table = frappe.db.sql(
			f"""
			SHOW INDEX FROM tab{self.test_table_name}
			WHERE Key_name = '{index_name}';
			"""
		)
		self.assertEquals(len(indexs_in_table), 2)


class TestDBSetValue(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.todo1 = frappe.get_doc(doctype="ToDo", description="test_set_value 1").insert()
		cls.todo2 = frappe.get_doc(doctype="ToDo", description="test_set_value 2").insert()

	def test_update_single_doctype_field(self):
		value = frappe.db.get_single_value("System Settings", "deny_multiple_sessions")
		changed_value = not value

		frappe.db.set_value("System Settings", "System Settings", "deny_multiple_sessions", changed_value)
		current_value = frappe.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

		changed_value = not current_value
		frappe.db.set_value("System Settings", None, "deny_multiple_sessions", changed_value)
		current_value = frappe.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

		changed_value = not current_value
		frappe.db.set_single_value("System Settings", "deny_multiple_sessions", changed_value)
		current_value = frappe.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

	def test_update_single_row_single_column(self):
		frappe.db.set_value("ToDo", self.todo1.name, "description", "test_set_value change 1")
		updated_value = frappe.db.get_value("ToDo", self.todo1.name, "description")
		self.assertEqual(updated_value, "test_set_value change 1")

	def test_update_single_row_multiple_columns(self):
		description, status = "Upated by test_update_single_row_multiple_columns", "Closed"

		frappe.db.set_value("ToDo", self.todo1.name, {
			"description": description,
			"status": status,
		}, update_modified=False)

		updated_desciption, updated_status = frappe.db.get_value("ToDo",
			filters={"name": self.todo1.name},
			fieldname=["description", "status"]
		)

		self.assertEqual(description, updated_desciption)
		self.assertEqual(status, updated_status)

	def test_update_multiple_rows_single_column(self):
		frappe.db.set_value("ToDo", {"description": ("like", "%test_set_value%")}, "description", "change 2")

		self.assertEqual(frappe.db.get_value("ToDo", self.todo1.name, "description"), "change 2")
		self.assertEqual(frappe.db.get_value("ToDo", self.todo2.name, "description"), "change 2")

	def test_update_multiple_rows_multiple_columns(self):
		todos_to_update = frappe.get_all("ToDo", filters={
			"description": ("like", "%test_set_value%"),
			"status": ("!=", "Closed")
		}, pluck="name")

		frappe.db.set_value("ToDo", {
			"description": ("like", "%test_set_value%"),
			"status": ("!=", "Closed")
		}, {
			"status": "Closed",
			"priority": "High"
		})

		test_result = frappe.get_all("ToDo", filters={"name": ("in", todos_to_update)}, fields=["status", "priority"])

		self.assertTrue(all(x for x in test_result if x["status"] == "Closed"))
		self.assertTrue(all(x for x in test_result if x["priority"] == "High"))

	def test_update_modified_options(self):
		self.todo2.reload()

		todo = self.todo2
		updated_description = f"{todo.description} - by `test_update_modified_options`"
		custom_modified = datetime.datetime.fromisoformat(add_days(now(), 10))
		custom_modified_by = "user_that_doesnt_exist@example.com"

		frappe.db.set_value("ToDo", todo.name, "description", updated_description, update_modified=False)
		self.assertEqual(updated_description, frappe.db.get_value("ToDo", todo.name, "description"))
		self.assertEqual(todo.modified, frappe.db.get_value("ToDo", todo.name, "modified"))

		frappe.db.set_value("ToDo", todo.name, "description", "test_set_value change 1", modified=custom_modified, modified_by=custom_modified_by)
		self.assertTupleEqual(
			(custom_modified, custom_modified_by),
			frappe.db.get_value("ToDo", todo.name, ["modified", "modified_by"])
		)

	def test_for_update(self):
		self.todo1.reload()

		with patch.object(Database, "sql") as sql_called:
			frappe.db.set_value(
				self.todo1.doctype,
				self.todo1.name,
				"description",
				f"{self.todo1.description}-edit by `test_for_update`"
			)
			first_query = sql_called.call_args_list[0].args[0]
			second_query = sql_called.call_args_list[1].args[0]

			self.assertTrue(sql_called.call_count == 2)
			self.assertTrue("FOR UPDATE" in first_query)
			if frappe.conf.db_type == "postgres":
				from frappe.database.postgres.database import modify_query
				self.assertTrue(modify_query("UPDATE `tabToDo` SET") in second_query)
			if frappe.conf.db_type == "mariadb":
				self.assertTrue("UPDATE `tabToDo` SET" in second_query)

	def test_cleared_cache(self):
		self.todo2.reload()

		with patch.object(frappe, "clear_document_cache") as clear_cache:
			frappe.db.set_value(
				self.todo2.doctype,
				self.todo2.name,
				"description",
				f"{self.todo2.description}-edit by `test_cleared_cache`"
			)
			clear_cache.assert_called()

	def test_update_alias(self):
		args = (self.todo1.doctype, self.todo1.name, "description", "Updated by `test_update_alias`")
		kwargs = {"for_update": False, "modified": None, "modified_by": None, "update_modified": True, "debug": False}

		self.assertTrue("return self.set_value(" in inspect.getsource(frappe.db.update))

		with patch.object(Database, "set_value") as set_value:
			frappe.db.update(*args, **kwargs)
			set_value.assert_called_once()
			set_value.assert_called_with(*args, **kwargs)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()


@run_only_if(db_type_is.POSTGRES)
class TestDDLCommandsPost(unittest.TestCase):
	test_table_name = "TestNotes"

	def setUp(self) -> None:
		frappe.db.sql(
			f"""
			CREATE TABLE "tab{self.test_table_name}" ("id" INT NULL, content text, PRIMARY KEY ("id"))
			"""
		)

	def tearDown(self) -> None:
		frappe.db.sql(f'DROP TABLE "tab{self.test_table_name}"')
		self.test_table_name = "TestNotes"

	def test_rename(self) -> None:
		new_table_name = f"{self.test_table_name}_new"
		frappe.db.rename_table(self.test_table_name, new_table_name)
		check_exists = frappe.db.sql(
			f"""
			SELECT EXISTS (
			SELECT FROM information_schema.tables
			WHERE  table_name = 'tab{new_table_name}'
			);
			"""
		)
		self.assertTrue(check_exists[0][0])

		# * so this table is deleted after the rename
		self.test_table_name = new_table_name

	def test_describe(self) -> None:
		self.assertEqual(
			[("id",), ("content",)], frappe.db.describe(self.test_table_name)
		)

	def test_change_type(self) -> None:
		frappe.db.change_column_type(self.test_table_name, "id", "varchar(255)")
		check_change = frappe.db.sql(
			f"""
			SELECT
				table_name,
				column_name,
				data_type
			FROM
				information_schema.columns
			WHERE
				table_name = 'tab{self.test_table_name}'
			"""
		)
		self.assertGreater(len(check_change), 0)
		self.assertIn("character varying", check_change[0])

	def test_add_index(self) -> None:
		index_name = "test_index"
		frappe.db.add_index(self.test_table_name, ["id", "content(50)"], index_name)
		indexs_in_table = frappe.db.sql(
			f"""
			SELECT indexname
			FROM pg_indexes
			WHERE tablename = 'tab{self.test_table_name}'
			AND indexname = '{index_name}' ;
			""",
		)
		self.assertEquals(len(indexs_in_table), 1)

	@run_only_if(db_type_is.POSTGRES)
	def test_modify_query(self):
		from frappe.database.postgres.database import modify_query

		query = "select * from `tabtree b` where lft > 13 and rgt <= 16 and name =1.0 and parent = 4134qrsdc and isgroup = 1.00045"
		self.assertEqual(
			"select * from \"tabtree b\" where lft > \'13\' and rgt <= '16' and name = '1' and parent = 4134qrsdc and isgroup = 1.00045",
			modify_query(query)
		)

		query = "select locate(\".io\", \"frappe.io\"), locate(\"3\", cast(3 as varchar)), locate(\"3\", 3::varchar)"
		self.assertEqual(
			"select strpos( \"frappe.io\", \".io\"), strpos( cast(3 as varchar), \"3\"), strpos( 3::varchar, \"3\")",
			modify_query(query)
		)

	@run_only_if(db_type_is.POSTGRES)
	def test_modify_values(self):
		from frappe.database.postgres.database import modify_values

		self.assertEqual(
			{"abcd": "23", "efgh": "23", "ijkl": 23.0345, "mnop": "wow"},
			modify_values({"abcd": 23, "efgh": 23.0, "ijkl": 23.0345, "mnop": "wow"})
		)
		self.assertEqual(
			["23", "23", 23.00004345, "wow"],
			modify_values((23, 23.0, 23.00004345, "wow"))
		)

	def test_sequence_table_creation(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		dt = new_doctype("autoinc_dt_seq_test", autoincremented=True).insert(ignore_permissions=True)

		if frappe.db.db_type == "postgres":
			self.assertTrue(
				frappe.db.sql("""select sequence_name FROM information_schema.sequences
				where sequence_name ilike 'autoinc_dt_seq_test%'""")[0][0]
			)
		else:
			self.assertTrue(
				frappe.db.sql("""select data_type FROM information_schema.tables
				where table_type = 'SEQUENCE' and table_name like 'autoinc_dt_seq_test%'""")[0][0]
			)

		dt.delete(ignore_permissions=True)
