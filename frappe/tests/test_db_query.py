# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.page.permission_manager.permission_manager import add, reset, update
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.database.utils import DefaultOrderBy
from frappe.desk.reportview import get_filters_cond
from frappe.handler import execute_cmd
from frappe.model.db_query import DatabaseQuery, get_between_date_filter
from frappe.permissions import add_user_permission, clear_user_permissions_for_doctype
from frappe.query_builder import Field
from frappe.tests import IntegrationTestCase
from frappe.tests.test_helpers import setup_for_tests
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.testutils import add_custom_field, clear_custom_fields

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]


@contextmanager
def setup_test_user(set_user=False):
	test_user = frappe.get_doc("User", "test@example.com")
	user_roles = frappe.get_roles()
	test_user.remove_roles(*user_roles)
	test_user.add_roles("Blogger")

	if set_user:
		frappe.set_user(test_user.name)

	yield test_user

	test_user.reload()
	test_user.remove_roles("Blogger")
	test_user.add_roles(*user_roles)


@contextmanager
def setup_patched_blog_post():
	add_child_table_to_blog_post()
	make_property_setter("Test Blog Post", "published", "permlevel", 1, "Int")
	reset("Test Blog Post")
	add("Test Blog Post", "Website Manager", 1)
	update("Test Blog Post", "Website Manager", 1, "write", 1)
	yield


@contextmanager
def setup_autoincrement_link_doctypes():
	target_dt_name = "Test Auto Link Target"
	source_dt_name = "Test Auto Link Source"

	frappe.delete_doc_if_exists("DocType", source_dt_name, force=True)
	frappe.delete_doc_if_exists("DocType", target_dt_name, force=True)

	try:
		new_doctype(
			target_dt_name,
			autoname="autoincrement",
			fields=[{"label": "Target Title", "fieldname": "target_title", "fieldtype": "Data"}],
		).insert(ignore_permissions=True)
		new_doctype(
			source_dt_name,
			fields=[
				{
					"label": "Link Field",
					"fieldname": "link_field",
					"fieldtype": "Link",
					"options": target_dt_name,
				}
			],
		).insert(ignore_permissions=True)

		target_doc = frappe.get_doc(doctype=target_dt_name, target_title="Target").insert(
			ignore_permissions=True
		)
		source_doc = frappe.get_doc(doctype=source_dt_name, link_field=target_doc.name).insert(
			ignore_permissions=True
		)
		yield target_dt_name, source_dt_name, target_doc, source_doc
	finally:
		frappe.delete_doc_if_exists("DocType", source_dt_name, force=True)
		frappe.delete_doc_if_exists("DocType", target_dt_name, force=True)


@contextmanager
def setup_autoincrement_parent_doctypes():
	child_dt_name = "Test Auto Parent Child"
	parent_dt_name = "Test Auto Parent"

	frappe.delete_doc_if_exists("DocType", parent_dt_name, force=True)
	frappe.delete_doc_if_exists("DocType", child_dt_name, force=True)

	try:
		new_doctype(
			child_dt_name,
			istable=1,
			fields=[{"label": "Child Value", "fieldname": "child_value", "fieldtype": "Data"}],
		).insert(ignore_permissions=True)
		new_doctype(
			parent_dt_name,
			autoname="autoincrement",
			fields=[
				{
					"label": "Child Table",
					"fieldname": "child_table",
					"fieldtype": "Table",
					"options": child_dt_name,
				}
			],
		).insert(ignore_permissions=True)

		parent_doc = frappe.get_doc(doctype=parent_dt_name, child_table=[{"child_value": "Child"}]).insert(
			ignore_permissions=True
		)
		yield parent_dt_name, child_dt_name, parent_doc
	finally:
		frappe.delete_doc_if_exists("DocType", parent_dt_name, force=True)
		frappe.delete_doc_if_exists("DocType", child_dt_name, force=True)


class TestDBQuery(IntegrationTestCase):
	def setUp(self):
		setup_for_tests()
		frappe.set_user("Administrator")

	def test_basic(self):
		self.assertTrue({"name": "DocType"} in DatabaseQuery("DocType").execute(limit_page_length=None))

	def test_extract_tables(self):
		db_query = DatabaseQuery("DocType")
		add_custom_field("DocType", "test_tab_field", "Data")

		db_query.fields = [
			"tabNote.creation",
			"test_tab_field",
			"tabDocType.test_tab_field",
		]
		db_query.extract_tables()
		self.assertIn("`tabNote`", db_query.tables)
		self.assertIn("`tabDocType`", db_query.tables)
		self.assertNotIn("test_tab_field", db_query.tables)

		clear_custom_fields("DocType")

	def test_child_table_field_syntax(self):
		note = frappe.get_doc(
			doctype="Note",
			title=f"Test {frappe.utils.random_string(8)}",
			content="test",
			seen_by=[{"user": "Administrator"}],
		).insert()
		result = frappe.get_all(
			"Note",
			filters={"name": note.name},
			fields=["name", "seen_by.user as seen_by"],
			limit=1,
		)
		self.assertEqual(result[0].seen_by, "Administrator")
		note.delete()

	def test_child_table_join(self):
		frappe.delete_doc_if_exists("DocType", "Parent DocType 1")
		frappe.delete_doc_if_exists("DocType", "Parent DocType 2")
		frappe.delete_doc_if_exists("DocType", "Child DocType")
		# child table
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Child DocType",
				"module": "Custom",
				"custom": 1,
				"istable": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				],
			}
		).insert()
		# doctype 1
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Parent DocType 1",
				"module": "Custom",
				"autoname": "Prompt",
				"custom": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
					{
						"label": "Table Field 1",
						"fieldname": "child",
						"fieldtype": "Table",
						"options": "Child DocType",
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()
		# doctype 2
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Parent DocType 2",
				"autoname": "Prompt",
				"module": "Custom",
				"custom": 1,
				"fields": [
					{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
					{
						"label": "Table Field 1",
						"fieldname": "child",
						"fieldtype": "Table",
						"options": "Child DocType",
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()

		# clear records
		frappe.db.delete("Parent DocType 1")
		frappe.db.delete("Parent DocType 2")
		frappe.db.delete("Child DocType")

		# insert records
		frappe.get_doc(
			doctype="Parent DocType 1",
			title="test",
			child=[
				{"title": "parent 1 child record 1"},
				{"title": "parent 1 child record 2"},
			],
			__newname="test_parent",
		).insert(ignore_if_duplicate=True)
		frappe.get_doc(
			doctype="Parent DocType 2",
			title="test",
			child=[{"title": "parent 2 child record 1"}],
			__newname="test_parent",
		).insert(ignore_if_duplicate=True)

		# test query
		results1 = frappe.get_all("Parent DocType 1", fields=["name", "child.title as child_title"])
		results2 = frappe.get_all("Parent DocType 2", fields=["name", "child.title as child_title"])
		# check both parents have same name
		self.assertEqual(results1[0].name, results2[0].name)
		# check both parents have different number of child records
		self.assertEqual(len(results1), 2)
		self.assertEqual(len(results2), 1)
		parent1_children = [result.child_title for result in results1]
		self.assertIn("parent 1 child record 1", parent1_children)
		self.assertIn("parent 1 child record 2", parent1_children)
		self.assertEqual(results2[0].child_title, "parent 2 child record 1")

	def make_note(self, seen_by=None):
		note = frappe.get_doc(
			doctype="Note",
			title=f"test exists filter {frappe.generate_hash(length=8)}",
			content="test",
			seen_by=[{"user": user} for user in (seen_by or [])],
		).insert()
		self.addCleanup(note.delete)
		return note

	def assert_note_filter_results(self, filters, includes=(), excludes=(), or_filters=None):
		for result in (
			frappe.get_all("Note", filters=filters, or_filters=or_filters, pluck="name"),
			DatabaseQuery("Note").execute(filters=filters, or_filters=or_filters, pluck="name"),
		):
			for name in includes:
				self.assertIn(name, result)
			for name in excludes:
				self.assertNotIn(name, result)

	def test_child_table_filter_uses_exists(self):
		"""Filter-only child tables filter via exists() — no join, no group by needed."""
		note = self.make_note(seen_by=["Administrator"])

		result = frappe.get_all(
			"Note",
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name", "title"],
		)
		self.assertIn(note.name, [r.name for r in result])

		query = DatabaseQuery("Note")
		sql = query.execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]], fields=["name", "title"], run=0
		)
		self.assertEqual(query.tables, ["`tabNote`"])
		self.assertIn("exists (", sql)

		# the dedup group by sent by list views is dropped once nothing multiplies rows
		sql = DatabaseQuery("Note").execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name", "title"],
			group_by="`tabNote`.`name`",
			run=0,
		)
		self.assertNotIn("group by", sql)

	def test_child_table_filter_with_link_field_fetch(self):
		"""Full list view repro of GH-39851: child-table filter + link table column in
		fields (show_title_field_in_link) + dedup group by. Raised GroupingError on
		PostgreSQL when the group by survived alongside the link table column."""
		# live engine (frappe.model.qb_query via get_all)
		result = frappe.get_all(
			"User",
			filters=[["Has Role", "role", "=", "System Manager"]],
			fields=["name", "language.language_name as language_title"],
			group_by="`tabUser`.`name`",
			order_by="`tabUser`.`modified` desc",
		)
		self.assertIn("Administrator", [r.name for r in result])

		# legacy engine
		result = DatabaseQuery("User").execute(
			filters=[["Has Role", "role", "=", "System Manager"]],
			fields=["name", "language.language_name as language_title"],
			group_by="`tabUser`.`name`",
			order_by="`tabUser`.`modified` desc",
		)
		self.assertIn("Administrator", [r.name for r in result])

	def test_child_table_filter_matches_parents_without_child_rows(self):
		"""Parents with no child rows must keep matching "empty" style filters,
		exactly like the left join these filters used before."""
		childless = self.make_note()
		seen = self.make_note(seen_by=["Administrator"])

		self.assert_note_filter_results(
			[["Note Seen By", "user", "is", "not set"]], includes=[childless.name], excludes=[seen.name]
		)
		self.assert_note_filter_results(
			[["Note Seen By", "user", "!=", "Administrator"]],
			includes=[childless.name],
			excludes=[seen.name],
		)
		self.assert_note_filter_results(
			[["Note Seen By", "user", "=", "Administrator"]],
			includes=[seen.name],
			excludes=[childless.name],
		)

	def test_child_table_filters_match_same_child_row(self):
		"""Multiple filters on one child table must all match the same child row,
		like they did against a single joined table."""
		note = self.make_note(seen_by=["Administrator", "Guest"])

		# legacy engine not asserted here: Filters normalization coalesces the two
		# `=` filters into one `in` filter before they reach the query
		result = frappe.get_all(
			"Note",
			filters=[
				["Note Seen By", "user", "=", "Administrator"],
				["Note Seen By", "user", "=", "Guest"],
			],
			pluck="name",
		)
		self.assertNotIn(note.name, result)

		self.assert_note_filter_results(
			[
				["Note Seen By", "user", "=", "Administrator"],
				["Note Seen By", "user", "like", "Admin%"],
			],
			includes=[note.name],
		)
		self.assert_note_filter_results(
			[
				["Note Seen By", "user", "!=", "Guest"],
				["Note Seen By", "user", "like", "Admin%"],
			],
			includes=[note.name],
		)

	def test_child_table_or_filters_via_exists(self):
		note = self.make_note(seen_by=["Administrator"])

		result = frappe.get_all(
			"Note",
			filters={"name": note.name},
			or_filters=[
				["Note Seen By", "user", "=", "Administrator"],
				["Note Seen By", "user", "=", "some-nonexistent-user"],
			],
			pluck="name",
		)
		self.assertEqual(result, [note.name])

		query = DatabaseQuery("Note")
		query.execute(
			filters={"name": note.name},
			or_filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name"],
			run=0,
		)
		self.assertEqual(query.tables, ["`tabNote`"])

		result = DatabaseQuery("Note").execute(
			filters={"name": note.name},
			or_filters=[
				["Note Seen By", "user", "=", "Administrator"],
				["Note Seen By", "user", "=", "some-nonexistent-user"],
			],
			pluck="name",
		)
		self.assertEqual(result, [note.name])

	def test_child_table_filter_in_both_filter_groups_uses_join(self):
		"""A child table filtered in both filters and or_filters keeps the legacy
		join so that both groups test the same joined child row."""
		query = DatabaseQuery("Note")
		sql = query.execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			or_filters=[["Note Seen By", "user", "=", "Guest"]],
			fields=["name"],
			run=0,
		)
		self.assertIn("`tabNote Seen By`", query.tables)
		self.assertNotIn("exists (", sql)

		# the surviving dedup group by must not break when link table columns are
		# selected (GH-39851 with the join fallback)
		result = DatabaseQuery("User").execute(
			filters=[["Has Role", "role", "=", "System Manager"]],
			or_filters=[["Has Role", "role", "=", "Guest"], ["User", "enabled", "=", 1]],
			fields=["name", "modified", "language.language_name as language_title"],
			group_by="`tabUser`.`name`",
			order_by="modified desc",
		)
		self.assertIn("Administrator", [r.name for r in result])

	def test_child_table_in_fields_still_uses_join(self):
		"""A child table that is selected stays joined; its filters apply to the join."""
		note = self.make_note(seen_by=["Administrator"])

		result = frappe.get_all(
			"Note",
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name", "`tabNote Seen By`.user as seen_user"],
		)
		self.assertIn(note.name, [r.name for r in result])

		query = DatabaseQuery("Note")
		query.execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name", "`tabNote Seen By`.user"],
			run=0,
		)
		self.assertIn("`tabNote Seen By`", query.tables)

	def test_child_table_filter_with_aggregate_field_keeps_join(self):
		note = self.make_note(seen_by=["Administrator", "Guest"])

		query = DatabaseQuery("Note")
		result = query.execute(
			filters=[
				["Note", "name", "=", note.name],
				["Note Seen By", "user", "in", ["Administrator", "Guest"]],
			],
			fields=["count(`tabNote Seen By`.`name`) as seen_count"],
		)
		self.assertIn("`tabNote Seen By`", query.tables)
		self.assertEqual(result[0].seen_count, 2)

	def test_child_table_filter_with_child_order_by_keeps_join(self):
		note = self.make_note(seen_by=["Administrator"])

		query = DatabaseQuery("Note")
		result = query.execute(
			filters=[["Note", "name", "=", note.name], ["Note Seen By", "user", "=", "Administrator"]],
			fields=["name"],
			order_by="`tabNote Seen By`.`user` asc",
			pluck="name",
		)
		self.assertIn("`tabNote Seen By`", query.tables)
		self.assertEqual(result, [note.name])

		query = DatabaseQuery("Note")
		query.execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name"],
			group_by="`tabNote Seen By`.`user`",
			run=0,
		)
		self.assertIn("`tabNote Seen By`", query.tables)

		# unquoted and double-quoted references must keep the join too
		for group_by in ("tabNote Seen By.user", '"tabNote Seen By".user'):
			query = DatabaseQuery("Note")
			query.execute(
				filters=[["Note Seen By", "user", "=", "Administrator"]],
				fields=["name"],
				group_by=group_by,
				run=0,
			)
			self.assertIn("`tabNote Seen By`", query.tables)

	def test_child_table_filter_with_childnames_keeps_join(self):
		query = DatabaseQuery("Note")
		query.execute(
			filters=[["Note Seen By", "user", "=", "Administrator"]],
			fields=["name"],
			with_childnames=True,
			run=0,
		)
		self.assertIn("`tabNote Seen By`", query.tables)

	def test_child_table_filter_with_permission_script_keeps_join(self):
		import frappe.model.db_query as db_query_module

		with (
			patch.object(
				db_query_module,
				"get_server_script_map",
				return_value={"permission_query": {"Note": "test-script"}},
			),
			patch.object(DatabaseQuery, "get_permission_query_conditions", return_value=""),
		):
			query = DatabaseQuery("Note")
			sql = query.execute(
				filters=[["Note Seen By", "user", "=", "Administrator"]], fields=["name"], run=0
			)

		self.assertIn("`tabNote Seen By`", query.tables)
		self.assertNotIn("exists (", sql)

	def test_link_field_syntax(self):
		todo = frappe.get_doc(doctype="ToDo", description="Test ToDo", allocated_to="Administrator").insert()
		result = frappe.get_all(
			"ToDo",
			filters={"name": todo.name},
			fields=["name", "allocated_to.email as allocated_user_email"],
			limit=1,
		)
		self.assertEqual(result[0].allocated_user_email, "admin@example.com")
		todo.delete()

	def test_autoincrement_link_field_join(self):
		with setup_autoincrement_link_doctypes() as (
			_target_dt_name,
			source_dt_name,
			target_doc,
			source_doc,
		):
			query = DatabaseQuery(source_dt_name).execute(
				fields=["name", "link_field.target_title"],
				filters={"name": source_doc.name},
				run=False,
			)
			result = DatabaseQuery(source_dt_name).execute(
				fields=["name", "link_field.target_title"],
				filters={"name": source_doc.name},
			)

			self.assertEqual(result[0].target_title, target_doc.target_title)
			if frappe.db.db_type == "postgres":
				self.assertIn('CAST("TABTEST AUTO LINK TARGET_1"."NAME" AS VARCHAR)', query.upper())
			else:
				self.assertNotIn("CAST(", query.upper())

	def test_autoincrement_child_table_join(self):
		with setup_autoincrement_parent_doctypes() as (parent_dt_name, child_dt_name, parent_doc):
			result = DatabaseQuery(parent_dt_name).execute(
				fields=["name", f"`tab{child_dt_name}`.child_value"],
				filters=[
					[parent_dt_name, "name", "=", parent_doc.name],
					[child_dt_name, "child_value", "=", "Child"],
				],
			)

			self.assertEqual(len(result), 1)
			self.assertEqual(result[0].child_value, "Child")

	def test_build_match_conditions(self):
		clear_user_permissions_for_doctype("Test Blog Post", "test2@example.com")

		test2user = frappe.get_doc("User", "test2@example.com")
		test2user.add_roles("Blogger")
		frappe.set_user("test2@example.com")

		# this will get match conditions for Blog Post
		build_match_conditions = DatabaseQuery("Test Blog Post").build_match_conditions

		# Before any user permission is applied
		# get as filters
		self.assertEqual(build_match_conditions(as_condition=False), [])
		# get as conditions
		self.assertEqual(build_match_conditions(as_condition=True), "")

		add_user_permission("Test Blog Post", "_Test Blog Post", "test2@example.com", True)
		add_user_permission("Test Blog Post", "_Test Blog Post 1", "test2@example.com", True)

		# After applying user permission
		# get as filters
		self.assertTrue(
			{"Test Blog Post": ["_Test Blog Post 1", "_Test Blog Post"]}
			in build_match_conditions(as_condition=False)
		)
		# get as conditions
		if frappe.db.db_type == "mariadb":
			assertion_string = """(((ifnull(`tabTest Blog Post`.`name`, '')='' or `tabTest Blog Post`.`name` in ('_Test Blog Post 1', '_Test Blog Post'))))"""
		elif frappe.db.db_type == "postgres":
			assertion_string = """(((ifnull(cast(`tabTest Blog Post`.`name` as varchar), '')='' or cast(`tabTest Blog Post`.`name` as varchar) in ('_Test Blog Post 1', '_Test Blog Post'))))"""

		self.assertEqual(build_match_conditions(as_condition=True), assertion_string)

		frappe.set_user("Administrator")

	def test_fields(self):
		self.assertTrue(
			{"name": "DocType", "issingle": 0}
			in DatabaseQuery("DocType").execute(fields=["name", "issingle"], limit_page_length=None)
		)

	def test_filters_1(self):
		self.assertFalse(
			{"name": "DocType"}
			in DatabaseQuery("DocType").execute(filters=[["DocType", "name", "like", "J%"]])
		)

	def test_filters_2(self):
		self.assertFalse(
			{"name": "DocType"} in DatabaseQuery("DocType").execute(filters=[{"name": ["like", "J%"]}])
		)

	def test_filters_3(self):
		self.assertFalse(
			{"name": "DocType"} in DatabaseQuery("DocType").execute(filters={"name": ["like", "J%"]})
		)

	def test_filters_4(self):
		self.assertTrue(
			{"name": "DocField"} in DatabaseQuery("DocType").execute(filters={"name": "DocField"})
		)

	def test_in_not_in_filters(self):
		self.assertFalse(DatabaseQuery("DocType").execute(filters={"name": ["in", None]}))
		self.assertTrue(
			{"name": "DocType"} in DatabaseQuery("DocType").execute(filters={"name": ["not in", None]})
		)

		for result in [{"name": "DocType"}, {"name": "DocField"}]:
			self.assertTrue(
				result in DatabaseQuery("DocType").execute(filters={"name": ["in", "DocType,DocField"]})
			)

		for result in [{"name": "DocType"}, {"name": "DocField"}]:
			self.assertFalse(
				result in DatabaseQuery("DocType").execute(filters={"name": ["not in", "DocType,DocField"]})
			)

	def test_in_filter_json_encoded_values(self):
		# JSON-encoded list string should work the same as comma-separated
		for result in [{"name": "DocType"}, {"name": "DocField"}]:
			self.assertTrue(
				result
				in DatabaseQuery("DocType").execute(filters={"name": ["in", '["DocType", "DocField"]']})
			)

		# Values containing commas must not be split
		todo = frappe.get_doc(
			doctype="ToDo", description="Test, With Comma", allocated_to="Administrator"
		).insert()
		try:
			results = DatabaseQuery("ToDo").execute(
				filters={"description": ["in", '["Test, With Comma"]']},
				fields=["description"],
			)
			self.assertIn({"description": "Test, With Comma"}, results)

			results_split = DatabaseQuery("ToDo").execute(
				filters={"description": ["in", "Test, With Comma"]},
				fields=["description"],
			)
			self.assertNotIn({"description": "Test, With Comma"}, results_split)
		finally:
			frappe.delete_doc("ToDo", todo.name)

	def test_string_as_field(self):
		self.assertEqual(
			frappe.get_all("DocType", as_list=True), frappe.get_all("DocType", fields="name", as_list=True)
		)

	def test_none_filter(self):
		query = frappe.qb.get_query("DocType", fields="name", filters={"restrict_to_domain": None})
		sql = str(query).replace("`", "").replace('"', "")
		condition = "restrict_to_domain IS NULL"
		self.assertIn(condition, sql)

	def test_or_filters(self):
		data = DatabaseQuery("DocField").execute(
			filters={"parent": "DocType"},
			fields=["fieldname", "fieldtype"],
			or_filters=[{"fieldtype": "Table"}, {"fieldtype": "Select"}],
		)

		self.assertTrue({"fieldtype": "Table", "fieldname": "fields"} in data)
		self.assertTrue({"fieldtype": "Select", "fieldname": "document_type"} in data)
		self.assertFalse({"fieldtype": "Check", "fieldname": "issingle"} in data)

	def test_between_filters(self):
		"""test case to check between filter for date fields"""
		frappe.db.delete("Event")

		# create events to test the between operator filter
		todays_event = create_event()
		event1 = create_event(starts_on="2016-07-05 23:59:59")
		event2 = create_event(starts_on="2016-07-06 00:00:00")
		event3 = create_event(starts_on="2016-07-07 23:59:59")
		event4 = create_event(starts_on="2016-07-08 00:00:00")

		# if the values are not passed in filters then event should be filter as current datetime
		data = DatabaseQuery("Event").execute(filters={"starts_on": ["between", None]}, fields=["name"])

		self.assertTrue({"name": event1.name} not in data)

		# if both from and to_date values are passed
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-06", "2016-07-07"]]},
			fields=["name"],
		)

		self.assertIn({"name": event2.name}, data)
		self.assertIn({"name": event3.name}, data)
		self.assertNotIn({"name": event1.name}, data)
		self.assertNotIn({"name": event4.name}, data)

		# if only one value is passed in the filter
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-07"]]}, fields=["name"]
		)

		self.assertIn({"name": event3.name}, data)
		self.assertIn({"name": event4.name}, data)
		self.assertIn({"name": todays_event.name}, data)
		self.assertNotIn({"name": event1.name}, data)
		self.assertNotIn({"name": event2.name}, data)

		# test between is formatted for creation column
		data = DatabaseQuery("Event").execute(
			filters={"creation": ["between", ["2016-07-06", "2016-07-07"]]},
			fields=["name"],
		)

	def test_between_filters_date_bounds(self):
		date_df = frappe._dict(fieldtype="Date")
		datetime_df = frappe._dict(fieldtype="Datetime")
		today = frappe.utils.nowdate()

		# No filters -> assumes today
		cond = get_between_date_filter("", date_df)
		self.assertQueryEqual(cond, f"'{today}' AND '{today}'")

		# One filter assumes "from" bound and to is today
		start = "2021-01-01"
		cond = get_between_date_filter([start], date_df)
		self.assertQueryEqual(cond, f"'{start}' AND '{today}'")

		# both date filters are applied
		start = "2021-01-01"
		end = "2022-01-02"
		cond = get_between_date_filter([start, end], date_df)
		self.assertQueryEqual(cond, f"'{start}' AND '{end}'")

		# single date should include entire day
		start = "2021-01-01"
		cond = get_between_date_filter([start, start], datetime_df)
		self.assertQueryEqual(cond, f"'{start} 00:00:00.000000' AND '{start} 23:59:59.999999'")

		# datetime field on datetime type should remain same
		start = "2021-01-01 01:01:00"
		end = "2022-01-02 12:23:43"
		cond = get_between_date_filter([start, end], datetime_df)
		self.assertQueryEqual(cond, f"'{start}.000000' AND '{end}.000000'")

	def test_ignore_permissions_for_get_filters_cond(self):
		frappe.set_user("test2@example.com")
		self.assertRaises(frappe.PermissionError, get_filters_cond, "DocType", dict(istable=1), [])
		self.assertTrue(get_filters_cond("DocType", dict(istable=1), [], ignore_permissions=True))
		frappe.set_user("Administrator")

	def test_query_fields_sanitizer(self):
		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle, version()"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=[
				"name",
				"issingle, IF(issingle=1, (select name from tabUser), count(name))",
			],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle, (select count(*) from tabSessions)"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle, SELECT LOCATE('', `tabUser`.`user`) AS user;"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=[
				"name",
				"issingle, IF(issingle=1, (SELECT name from tabUser), count(*))",
			],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle ''"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle,'"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "select * from tabSessions"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle from --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle from tabDocType order by 2 --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "1' UNION SELECT * FROM __Auth --"],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["@@version"],
			limit_start=0,
			limit_page_length=1,
		)

		data = DatabaseQuery("DocType").execute(
			fields=["count(`name`) as count"], limit_start=0, limit_page_length=1
		)
		self.assertTrue("count" in data[0])

		data = DatabaseQuery("DocType").execute(
			fields=["name", "issingle", "locate('','name') as _relevance"], limit_start=0, limit_page_length=1
		)
		self.assertTrue("_relevance" in data[0])

		# Test that fields with keywords in strings are allowed
		data = DatabaseQuery("DocType").execute(
			fields=["name", "locate('select', 'name')"],
			limit_start=0,
			limit_page_length=1,
		)
		self.assertTrue(data)

		# Test that subqueries with other DML are blocked
		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name", "issingle", "(insert into tabUser values (1))"],
			limit_start=0,
			limit_page_length=1,
		)

		data = DatabaseQuery("DocType").execute(
			fields=["name", "issingle", "date(creation) as creation"],
			limit_start=0,
			limit_page_length=1,
		)
		self.assertTrue("creation" in data[0])

		if frappe.db.db_type != "postgres":
			# datediff function does not exist in postgres
			data = DatabaseQuery("DocType").execute(
				fields=[
					"name",
					"issingle",
					"datediff(modified, creation) as date_diff",
				],
				limit_start=0,
				limit_page_length=1,
			)
			self.assertTrue("date_diff" in data[0])

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"name",
					"issingle",
					"if (issingle=1, (select name from tabUser), count(name))",
				],
				limit_start=0,
				limit_page_length=1,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"name",
					"issingle",
					"if(issingle=1, (select name from tabUser), count(name))",
				],
				limit_start=0,
				limit_page_length=1,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"name",
					"issingle",
					"( select name from `tabUser` where `tabDocType`.owner = `tabUser`.name )",
				],
				limit_start=0,
				limit_page_length=1,
				ignore_permissions=True,
			)

		with self.assertRaises(frappe.DataError):
			DatabaseQuery("DocType").execute(
				fields=[
					"name",
					"issingle",
					"(select name from `tabUser` where `tabDocType`.owner = `tabUser`.name )",
				],
				limit_start=0,
				limit_page_length=1,
			)

		# Ensure search terms aren't blocked as functions
		from frappe.desk.search import search_link

		search_terms = ("global", "user")

		for term in search_terms:
			with self.subTest(term=term):
				result = search_link("ToDo", term)
				self.assertIsInstance(result, list)

	def test_nested_permission(self):
		frappe.set_user("Administrator")
		create_nested_doctype()
		create_nested_doctype_records()
		clear_user_permissions_for_doctype("Nested DocType")

		# user permission for only one root folder
		add_user_permission("Nested DocType", "Level 1 A", "test2@example.com")

		from frappe.core.page.permission_manager.permission_manager import update

		# to avoid if_owner filter
		update("Nested DocType", "All", 0, "if_owner", 0)

		with self.set_user("test2@example.com"):
			data = DatabaseQuery("Nested DocType").execute()

		# children of root folder (for which we added user permission) should be accessible
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)

		# other folders should not be accessible
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		update("Nested DocType", "All", 0, "if_owner", 1)

	def test_filter_sanitizer(self):
		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name"],
			filters={"istable,": 1},
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name"],
			filters={"editable_grid,": 1},
			or_filters={"istable,": 1},
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name"],
			filters={"editable_grid,": 1},
			or_filters=[["DocType", "istable,", "=", 1]],
			limit_start=0,
			limit_page_length=1,
		)

		self.assertRaises(
			frappe.DataError,
			DatabaseQuery("DocType").execute,
			fields=["name"],
			filters={"editable_grid,": 1},
			or_filters=[
				["DocType", "istable", "=", 1],
				["DocType", "beta and 1=1", "=", 0],
			],
			limit_start=0,
			limit_page_length=1,
		)

		out = DatabaseQuery("DocType").execute(
			fields=["name"],
			filters={"editable_grid": 1, "module": "Core"},
			or_filters=[["DocType", "istable", "=", 1]],
			order_by="creation",
		)
		self.assertTrue("DocField" in [d["name"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["name"],
			filters={"issingle": 1},
			or_filters=[["DocType", "module", "=", "Core"]],
			order_by="creation",
		)
		self.assertTrue("Role Permission for Page and Report" in [d["name"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["name"],
			filters={"track_changes": 1, "module": "Core"},
			order_by="creation",
		)
		self.assertTrue("File" in [d["name"] for d in out])

		out = DatabaseQuery("DocType").execute(
			fields=["name"],
			filters=[
				["DocType", "ifnull(track_changes, 0)", "=", 0],
				["DocType", "module", "=", "Core"],
			],
			order_by="creation",
		)
		self.assertTrue("DefaultValue" in [d["name"] for d in out])

	def test_order_by_group_by_sanitizer(self):
		# order by with blacklisted function
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["name"],
				order_by="sleep (1) asc",
			)

		# group by with blacklisted function
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["name"],
				group_by="SLEEP(0)",
			)

		# sub query in order by
		with self.assertRaises(frappe.ValidationError):
			DatabaseQuery("DocType").execute(
				fields=["name"],
				order_by="(select rank from tabRankedDocTypes where tabRankedDocTypes.name = tabDocType.name) asc",
			)

		# validate allowed usage
		DatabaseQuery("DocType").execute(
			fields=["name"],
			order_by="name asc",
		)
		DatabaseQuery("DocType").execute(
			fields=["name"],
			order_by="name asc",
			group_by="name",
		)

		# check mariadb specific syntax
		if frappe.db.db_type == "mariadb":
			DatabaseQuery("DocType").execute(
				fields=["name"],
				order_by="timestamp(modified)",
			)

	def test_of_not_of_descendant_ancestors(self):
		frappe.set_user("Administrator")
		clear_user_permissions_for_doctype("Nested DocType")

		# in descendants filter
		data = frappe.get_all("Nested DocType", {"name": ("descendants of", "Level 2 A")})
		self.assertTrue({"name": "Level 3 A"} in data)

		data = frappe.get_all("Nested DocType", {"name": ("descendants of", "Level 1 A")})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertFalse({"name": "Level 1 A"} in data)
		self.assertFalse({"name": "Root"} in data)

		# in ancestors of filter
		data = frappe.get_all("Nested DocType", {"name": ("ancestors of", "Level 2 A")})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"name": ("ancestors of", "Level 1 A")})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertFalse({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		# not descendants filter
		data = frappe.get_all("Nested DocType", {"name": ("not descendants of", "Level 2 A")})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"name": ("not descendants of", "Level 1 A")})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		# not ancestors of filter
		data = frappe.get_all("Nested DocType", {"name": ("not ancestors of", "Level 2 A")})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} not in data)
		self.assertTrue({"name": "Root"} not in data)

		data = frappe.get_all("Nested DocType", {"name": ("not ancestors of", "Level 1 A")})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertFalse({"name": "Root"} in data)

		data = frappe.get_all("Nested DocType", {"name": ("ancestors of", "Root")})
		self.assertTrue(len(data) == 0)
		self.assertTrue(
			len(frappe.get_all("Nested DocType", {"name": ("not ancestors of", "Root")}))
			== len(frappe.get_all("Nested DocType"))
		)

	def test_is_set_is_not_set(self):
		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "not set"]})
		self.assertTrue({"name": "Integration Request"} in res)
		self.assertTrue({"name": "User"} in res)
		self.assertFalse({"name": "Blogger"} in res)

		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "set"]})
		self.assertTrue({"name": "DocField"} in res)
		self.assertTrue({"name": "Prepared Report"} in res)
		self.assertFalse({"name": "Property Setter"} in res)

		frappe.db.set_value("DocType", "Property Setter", "autoname", None, update_modified=False)

		res = DatabaseQuery("DocType").execute(filters={"autoname": ["is", "set"]})
		self.assertFalse({"name": "Property Setter"} in res)

	def test_set_field_tables(self):
		# Tests _in_standard_sql_methods method in test_set_field_tables
		# The following query will break if the above method is broken
		frappe.db.get_list(
			"Web Form",
			filters=[["Web Form Field", "reqd", "=", 1]],
			fields=[{"COUNT": "*", "as": "count"}],
			order_by="count desc",
			limit=50,
		)

	def test_virtual_field_get_list(self):
		try:
			frappe.get_list("Prepared Report", ["*"])
			frappe.get_list("Scheduled Job Type", ["*"])
		except Exception:
			print(frappe.get_traceback())
			self.fail("get_list not working with virtual field")

	def test_pluck_name(self):
		names = DatabaseQuery("DocType").execute(filters={"name": "DocType"}, pluck="name")
		self.assertEqual(names, ["DocType"])

	def test_pluck_any_field(self):
		owners = DatabaseQuery("DocType").execute(filters={"name": "DocType"}, pluck="owner")
		self.assertEqual(owners, ["Administrator"])

	def test_prepare_select_args(self):
		# frappe.get_all inserts modified field into order_by clause
		# test to make sure this is inserted into select field when postgres
		doctypes = frappe.get_all(
			"DocType",
			filters={"docstatus": 0, "document_type": ("!=", "")},
			group_by="document_type",
			fields=["document_type", {"SUM": "is_submittable", "as": "is_submittable"}],
			limit=1,
			as_list=True,
		)
		self.assertTrue(len(doctypes[0]) == 2)  # same for pg as well since we order_by None

	def test_field_comparison(self):
		"""Test DatabaseQuery.execute to test field comparison"""
		users_unedited = frappe.get_all(
			"User",
			filters={"creation": Field("modified")},
			fields=["name", "creation", "modified"],
			limit=1,
		)
		users_edited = frappe.get_all(
			"User",
			filters={"creation": ("!=", Field("modified"))},
			fields=["name", "creation", "modified"],
			limit=1,
		)

		self.assertEqual(users_unedited[0].modified, users_unedited[0].creation)
		self.assertNotEqual(users_edited[0].modified, users_edited[0].creation)

	def test_permlevel_fields(self):
		with setup_patched_blog_post(), setup_test_user(set_user=True):
			self.assertRaises(
				frappe.PermissionError,
				frappe.get_list,
				"Test Blog Post",
				filters={"published": 1},
				fields=["name", "published"],
				limit=1,
			)

			self.assertRaises(
				frappe.PermissionError,
				frappe.get_list,
				"Test Blog Post",
				filters={"published": 1},
				fields=["name", "`published`"],
				limit=1,
			)

			self.assertRaises(
				frappe.PermissionError,
				frappe.get_list,
				"Test Blog Post",
				filters={"published": 1},
				fields=["name", "`tabTest Blog Post`.`published`"],
				limit=1,
			)

			self.assertRaises(
				frappe.PermissionError,
				frappe.get_list,
				"Test Blog Post",
				filters={"published": 1},
				fields=["name", "`tabTest Child`.`test_field`"],
				limit=1,
			)

	def test_get_list_pluck_with_masked_fields(self):
		"""Regression for the pluck-on-masked-doctype crash and mask handling.

		For a non-admin user, a doctype with a masked field used to corrupt
		``frappe.db.get_list(..., pluck=<name>)`` results: ``mask_list_results``
		ran ``list(row)`` on each already-plucked scalar, so a string like
		"P-1156" came back as the tuple ('P','-','1','1','5','6') and a non-
		string value (int) raised ``TypeError`` on ``list(int)``.

		Since eb9bf4428e made masking opt-in on ``apply_permissions``, only
		permission-checking APIs (``frappe.db.get_list``) trigger masking.
		``frappe.db.get_values`` and ``get_query(..., ignore_permissions=True)``
		intentionally do not mask.
		"""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "Test Masked Pluck")
		new_doctype(
			"Test Masked Pluck",
			fields=[
				{"label": "Secret", "fieldname": "secret", "fieldtype": "Data", "mask": 1},
				{"label": "Amount", "fieldname": "amount", "fieldtype": "Int"},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "mask": 1},
				{"role": "Blogger", "read": 1},
			],
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc_if_exists, "DocType", "Test Masked Pluck")

		record = frappe.get_doc({"doctype": "Test Masked Pluck", "secret": "P-1156", "amount": 42}).insert(
			ignore_permissions=True
		)

		# Sanity: Administrator is never masked and gets the raw values.
		self.assertEqual(
			frappe.db.get_list("Test Masked Pluck", filters={"name": record.name}, pluck="name"),
			[record.name],
		)

		with setup_test_user(set_user=True):
			# `secret` is masked for this user, so the doctype has masked fields.
			self.assertTrue(frappe.get_meta("Test Masked Pluck").get_masked_fields())

			# Plucking a non-masked string field must return the scalar, not a
			# char tuple.
			self.assertEqual(
				frappe.db.get_list("Test Masked Pluck", filters={"name": record.name}, pluck="name"),
				[record.name],
			)

			# Plucking a non-masked int field must not raise (used to:
			# list(int) -> TypeError).
			self.assertEqual(
				frappe.db.get_list("Test Masked Pluck", filters={"name": record.name}, pluck="amount"),
				[42],
			)

			# Plucking the masked field itself returns the masked scalar value.
			self.assertEqual(
				frappe.db.get_list("Test Masked Pluck", filters={"name": record.name}, pluck="secret"),
				["XXXXXXXX"],
			)
		frappe.set_user("Administrator")

	def test_pluck_masks_field_wrapped_in_expression(self):
		"""Regression for expression-tree bypass in mask_pluck_results.

		Wrapping a masked field in a SQL function (Coalesce, Max, ...) or an
		arithmetic expression must still mask the plucked result. The prior
		check compared only ``fields[0].name`` — which returns the function
		name ('COALESCE', 'MAX') for wrappers and is missing for arithmetic —
		letting the raw value through.

		Uses ``qb.get_query(..., ignore_permissions=False)`` since direct
		``qb.from_(...).select(...).run()`` skips permission handling and
		therefore skips masking (per eb9bf4428e).
		"""
		from pypika import functions as fn

		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "Test Masked Pluck Wrapped")
		new_doctype(
			"Test Masked Pluck Wrapped",
			fields=[
				{"label": "Secret", "fieldname": "secret", "fieldtype": "Data", "mask": 1},
				{"label": "Amount", "fieldname": "amount", "fieldtype": "Int"},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "mask": 1},
				{"role": "Blogger", "read": 1},
			],
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc_if_exists, "DocType", "Test Masked Pluck Wrapped")

		record = frappe.get_doc(
			{"doctype": "Test Masked Pluck Wrapped", "secret": "P-1156", "amount": 42}
		).insert(ignore_permissions=True)

		def _pluck(field_expr):
			return frappe.qb.get_query(
				"Test Masked Pluck Wrapped",
				fields=[field_expr],
				filters={"name": record.name},
				ignore_permissions=False,
			).run(pluck=True)

		with setup_test_user(set_user=True):
			dt = frappe.qb.DocType("Test Masked Pluck Wrapped")

			# Coalesce(secret, fallback) — Coalesce returns the raw secret when
			# it is non-null, so the plucked result must be masked.
			self.assertEqual(_pluck(fn.Coalesce(dt.secret, "fb")), ["XXXXXXXX"])

			# Aggregation over the masked field — same principle.
			self.assertEqual(_pluck(fn.Max(dt.secret)), ["XXXXXXXX"])

			# Aliased wrapper — the alias must NOT hide the masked reference.
			self.assertEqual(_pluck(fn.Coalesce(dt.secret, "fb").as_("s")), ["XXXXXXXX"])

			# Non-masked field wrapped in a function — must NOT mask.
			self.assertEqual(_pluck(fn.Max(dt.amount)), [42])

		frappe.set_user("Administrator")

	def test_cast_name(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "autoinc_dt_test")
		dt = new_doctype("autoinc_dt_test", autoname="autoincrement").insert(ignore_permissions=True)

		query = DatabaseQuery("autoinc_dt_test").execute(
			fields=[
				"locate('1', `tabautoinc_dt_test`.`name`)",
				"name",
				"locate('1', name)",
			],
			filters={"name": 1},
			run=False,
		)

		if frappe.db.db_type == "postgres":
			self.assertTrue('strpos( cast("tabautoinc_dt_test"."name" as varchar), \'1\')' in query)
			self.assertTrue("strpos( cast(name as varchar), '1')" in query)
			self.assertTrue('where cast("tabautoinc_dt_test"."name" as varchar) = \'1\'' in query)
		else:
			self.assertTrue("locate('1', `tabautoinc_dt_test`.`name`)" in query)
			self.assertTrue("locate('1', name)" in query)
			self.assertTrue("where `tabautoinc_dt_test`.`name` = 1" in query)

		dt.delete(ignore_permissions=True)

	def test_fieldname_starting_with_int(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		frappe.delete_doc_if_exists("DocType", "dt_with_int_named_fieldname")
		frappe.delete_doc_if_exists("DocType", "table_dt")

		table_dt = new_doctype(
			"table_dt",
			istable=1,
			fields=[{"label": "1field", "fieldname": "2field", "fieldtype": "Data"}],
		).insert()

		dt = new_doctype(
			"dt_with_int_named_fieldname",
			fields=[
				{"label": "1field", "fieldname": "1field", "fieldtype": "Data"},
				{
					"label": "2table_field",
					"fieldname": "2table_field",
					"fieldtype": "Table",
					"options": table_dt.name,
				},
			],
		).insert(ignore_permissions=True)

		dt_data = frappe.get_doc({"doctype": "dt_with_int_named_fieldname", "1field": "10"}).insert(
			ignore_permissions=True
		)

		query = DatabaseQuery("dt_with_int_named_fieldname")
		self.assertTrue(query.execute(filters={"1field": "10"}))
		self.assertTrue(query.execute(filters={"1field": ["like", "1%"]}))
		self.assertTrue(query.execute(filters={"1field": ["in", "1,2,10"]}))
		self.assertTrue(query.execute(filters={"1field": ["is", "set"]}))
		self.assertFalse(query.execute(filters={"1field": ["not like", "1%"]}))
		self.assertTrue(query.execute(filters=[["table_dt", "2field", "is", "not set"]]))

		frappe.get_doc(
			{
				"doctype": table_dt.name,
				"2field": "10",
				"parent": dt_data.name,
				"parenttype": dt_data.doctype,
				"parentfield": "2table_field",
			}
		).insert(ignore_permissions=True)

		self.assertTrue(query.execute(filters=[["table_dt", "2field", "is", "set"]]))

		# cleanup
		dt.delete()
		table_dt.delete()

	def test_permission_query_condition(self):
		from frappe.desk.doctype.dashboard_settings.dashboard_settings import (
			create_dashboard_settings,
		)
		from frappe.model.db_query import DatabaseQuery

		self.doctype = "Dashboard Settings"
		self.user = "test'5@example.com"

		db_query = DatabaseQuery(self.doctype, user=self.user)

		permission_query_conditions = db_query.get_permission_query_conditions()

		create_dashboard_settings(self.user)

		dashboard_settings = frappe.db.sql(
			f"""
				SELECT name
				FROM `tabDashboard Settings`
				WHERE {permission_query_conditions}
			""",
			as_dict=1,
		)[0]

		self.assertTrue(dashboard_settings)

	def test_permission_query_condition_supports_pypika(self):
		"""The legacy DatabaseQuery path must also accept a pypika criterion from a hook."""
		from frappe.desk.doctype.dashboard_settings.dashboard_settings import (
			create_dashboard_settings,
		)
		from frappe.model.db_query import DatabaseQuery

		self.user = "test@example.com"
		create_dashboard_settings(self.user)

		with self.patch_hooks(
			{
				"permission_query_conditions": {
					"Dashboard Settings": ["frappe.tests.test_query.test_permission_hook_criterion"]
				}
			}
		):
			db_query = DatabaseQuery("Dashboard Settings", user=self.user)
			conditions = db_query.get_permission_query_conditions()

			# The criterion must be rendered to a namespaced SQL string (the `tab`-prefixed
			# table name is dialect-independent; only the surrounding quote char differs).
			self.assertIn("tabDashboard Settings", conditions)
			self.assertIn("name", conditions)

			# And the rendered string must be valid SQL that selects the user's record.
			rows = frappe.db.sql(
				f"SELECT name FROM `tabDashboard Settings` WHERE {conditions}",
				as_dict=True,
			)
			self.assertTrue(any(r.name == self.user for r in rows))

	def test_permission_criterion_escapes_values_safely(self):
		"""Values inside a pypika permission criterion must be driver-escaped, not inlined raw.

		pypika's bare quote-doubling is unsafe on MariaDB (backslash is an escape char), so the
		legacy path must route values through frappe.db.escape. A backslash must be doubled and a
		quote-breakout attempt must stay inside the string literal.
		"""
		from frappe.model.db_query import DatabaseQuery

		payload = "back\\slash' OR 1=1 -- "
		Dashboard = frappe.qb.DocType("Dashboard Settings")
		rendered = DatabaseQuery("Dashboard Settings")._render_permission_criterion(Dashboard.name == payload)

		# The value must appear exactly as frappe.db.escape produces it (driver-quality escaping:
		# backslash doubled, quote escaped) — never the raw breakout sequence.
		self.assertIn(frappe.db.escape(payload), rendered)
		self.assertNotIn("slash' OR", rendered)

	def test_virtual_doctype(self):
		"""Test that virtual doctypes can be queried using get_all"""

		virtual_doctype = new_doctype("Virtual DocType")
		virtual_doctype.is_virtual = 1
		virtual_doctype.insert(ignore_if_duplicate=True)

		class VirtualDocType:
			@staticmethod
			def get_list(args=None, limit_page_length=0, doctype=None):
				from frappe.types.filter import FilterTuple

				# Backward compatibility
				self.assertEqual(
					args["filters"], [FilterTuple(doctype="Virtual DocType", fieldname="name", value="test")]
				)

				self.assertEqual(limit_page_length, 1)
				self.assertEqual(doctype, "Virtual DocType")

		with patch(
			"frappe.controllers",
			new={frappe.local.site: {"Virtual DocType": VirtualDocType}},
		):
			frappe.get_all("Virtual DocType", filters={"name": "test"}, fields=["name"], limit=1)

	def test_function_alias_in_clauses(self):
		result = frappe.get_list(
			"ToDo",
			fields=["status", {"COUNT": "1", "as": "count"}],
			group_by="status",
			order_by="count desc",
			limit=1,
		)
		self.assertTrue(result)
		self.assertIn("count", result[0])

	def test_coalesce_with_in_ops(self):
		self.assertNotIn("IF", frappe.get_all("User", {"first_name": ("in", ["a", "b"])}, run=0).get_sql())
		self.assertIn("IFNULL", frappe.get_all("User", {"first_name": ("in", ["a", None])}, run=0).get_sql())
		self.assertIn("IFNULL", frappe.get_all("User", {"first_name": ("in", ["a", ""])}, run=0).get_sql())
		# Empty list with IN should return 1=0, not use IFNULL
		self.assertIn("1=0", frappe.get_all("User", {"first_name": ("in", [])}, run=0).get_sql())
		self.assertNotIn("IFNULL", frappe.get_all("User", {"first_name": ("in", [])}, run=0).get_sql())
		self.assertIn("IFNULL", frappe.get_all("User", {"first_name": ("not in", ["a"])}, run=0).get_sql())
		# Empty list with NOT IN should return 1=1, not use IFNULL
		self.assertIn("1=1", frappe.get_all("User", {"first_name": ("not in", [])}, run=0).get_sql())
		self.assertNotIn("IFNULL", frappe.get_all("User", {"first_name": ("not in", [])}, run=0).get_sql())
		self.assertIn("IFNULL", frappe.get_all("User", {"first_name": ("not in", [""])}, run=0).get_sql())

		# primary key is never nullable
		self.assertNotIn("IFNULL", frappe.get_all("User", {"name": ("in", ["a", None])}, run=0).get_sql())
		self.assertNotIn("IFNULL", frappe.get_all("User", {"name": ("in", ["a", ""])}, run=0).get_sql())
		self.assertNotIn("IFNULL", frappe.get_all("User", {"name": ("in", (""))}, run=0).get_sql())
		# Empty tuple with IN should return 1=0, not use IFNULL
		self.assertIn("1=0", frappe.get_all("User", {"name": ("in", ())}, run=0).get_sql())
		self.assertNotIn("IFNULL", frappe.get_all("User", {"name": ("in", ())}, run=0).get_sql())

	def test_coalesce_with_datetime_ops(self):
		self.assertNotIn(
			"IFNULL", frappe.get_all("User", {"last_active": (">", "2022-01-01")}, run=0).get_sql()
		)
		self.assertNotIn("IFNULL", frappe.get_all("User", {"creation": ("<", "2022-01-01")}, run=0).get_sql())
		self.assertNotIn(
			"IFNULL",
			frappe.get_all(
				"User", {"last_active": ("between", ("2022-01-01", "2023-01-01"))}, run=0
			).get_sql(),
		)
		self.assertIn("IFNULL", frappe.get_all("User", {"last_active": ("<", "2022-01-01")}, run=0).get_sql())

	def test_ambiguous_linked_tables(self):
		from frappe.desk.reportview import get

		if not frappe.db.exists("DocType", "Related Todos"):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"custom": 1,
					"module": "Custom",
					"name": "Related Todos",
					"naming_rule": "Random",
					"autoname": "hash",
					"fields": [
						{
							"label": "Todo One",
							"fieldname": "todo_one",
							"fieldtype": "Link",
							"options": "ToDo",
							"reqd": 1,
						},
						{
							"label": "Todo Two",
							"fieldname": "todo_two",
							"fieldtype": "Link",
							"options": "ToDo",
							"reqd": 1,
						},
					],
				}
			).insert()
		else:
			frappe.db.delete("Related Todos")

		todo_one = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Todo One",
			}
		).insert()

		todo_two = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Todo Two",
			}
		).insert()

		frappe.get_doc(
			{
				"doctype": "Related Todos",
				"todo_one": todo_one.name,
				"todo_two": todo_two.name,
			}
		).insert()

		frappe.form_dict.doctype = "Related Todos"
		frappe.form_dict.fields = [
			"`tabRelated Todos`.`name`",
			"`tabRelated Todos`.`todo_one`",
			"`tabRelated Todos`.`todo_two`",
			# because ToDo.show_title_as_field_link = 1
			"todo_one.description as todo_one_description",
			"todo_two.description as todo_two_description",
		]

		# Shouldn't raise pymysql.err.OperationalError: (1066, "Not unique table/alias: 'tabToDo'")
		data = get()
		self.assertEqual(len(data["values"]), 1)

	def test_select_star_expansion(self):
		count = frappe.get_list("Language", [{"SUM": 1}, {"COUNT": "*"}], as_list=1, order_by=None)[0]
		self.assertEqual(count[0], frappe.db.count("Language"))
		self.assertEqual(count[1], frappe.db.count("Language"))

	def test_ifnull_none(self):
		query = frappe.get_all("DocField", {"fieldname": None}, run=0).get_sql()
		self.assertIn("IS NULL", query)
		self.assertNotIn("\\'", query)
		self.assertNotIn("ifnull", query)
		self.assertFalse(frappe.get_all("DocField", {"name": None}))
		self.assertFalse(frappe.get_all("DocField", {"parent": None}))
		self.assertNotIn("0", frappe.get_all("DocField", {"parent": None}, run=0).get_sql())

	def test_ifnull_fallback_types(self):
		query = frappe.get_all("DocField", {"fieldname": ("!=", None)}, run=0).get_sql()
		# Fallbacks should always be of correct type
		self.assertIn("''", query)
		self.assertNotIn("0", query)
		self.assertNotIn("ifnull", query)


class TestReportView(IntegrationTestCase):
	def test_get_count(self):
		frappe.local.request = frappe._dict()
		frappe.local.request.method = "GET"

		# test with data check field
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocType", "show_title_field_in_link", "=", 1]],
				"fields": [],
				"distinct": "false",
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": {"show_title_field_in_link": 1},
				"distinct": "true",
			}
		)
		dict_filter_response = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertEqual(count, dict_filter_response)

		# test with child table filter
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocField", "fieldtype", "=", "Data"]],
				"fields": [],
				"distinct": "true",
			}
		)
		child_filter_response = execute_cmd("frappe.desk.reportview.get_count")
		current_value = frappe.db.sql(
			# the below query is equivalent to the one in reportview.get_count
			"select count(distinct `tabDocType`.name) as total_count"
			" from `tabDocType` left join `tabDocField`"
			" on (`tabDocField`.parenttype = 'DocType' and `tabDocField`.parent = `tabDocType`.name)"
			" where `tabDocField`.`fieldtype` = 'Data'"
		)[0][0]
		self.assertEqual(child_filter_response, current_value)

		# test with limit
		limit = 2
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"filters": [["DocType", "is_virtual", "=", 1]],
				"fields": [],
				"distinct": "false",
				"limit": limit,
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertLessEqual(count, limit)

		# test with distinct
		limit = 2
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"fields": [],
				"distinct": "true",
				"limit": limit,
			}
		)
		count = execute_cmd("frappe.desk.reportview.get_count")
		self.assertIsInstance(count, int)
		self.assertLessEqual(count, limit)

	def test_reportview_get(self):
		user = frappe.get_doc("User", "test@example.com")
		add_child_table_to_blog_post()

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles("Blogger")

		make_property_setter("Test Blog Post", "published", "permlevel", 1, "Int")
		reset("Test Blog Post")
		add("Test Blog Post", "Website Manager", 1)
		update("Test Blog Post", "Website Manager", 1, "write", 1)

		frappe.set_user(user.name)

		frappe.local.request = frappe._dict()
		frappe.local.request.method = "POST"

		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Test Blog Post",
				"fields": ["published", "title", "`tabTest Child`.`test_field`"],
			}
		)

		# even if * is passed, fields which are not accessible should be filtered out
		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["title"])
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Test Blog Post",
				"fields": ["*"],
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertNotIn("published", response["keys"])

		frappe.set_user("Administrator")
		user.add_roles("Website Manager")
		frappe.set_user(user.name)

		frappe.set_user("Administrator")

		# Admin should be able to see access all fields
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Test Blog Post",
				"fields": ["published", "title", "`tabTest Child`.`test_field`"],
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["published", "title", "test_field"])

		# reset user roles
		user.remove_roles("Blogger", "Website Manager")
		user.add_roles(*user_roles)

	def test_reportview_child_table_alias(self):
		from frappe.desk import reportview

		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"fields": ["name", "`tabDocField`.`fieldname` as 'DocField:fieldname'"],
				"limit": 1,
			}
		)
		response = reportview.get()
		self.assertIn("DocField:fieldname", response["keys"])
		self.assertNotIn("'DocField:fieldname'", response["keys"])

	def test_reportview_get_aggregation(self):
		# test aggregation based on child table field
		frappe.local.request = frappe._dict()
		frappe.local.request.method = "POST"
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "DocType",
				"fields": """["`tabDocField`.`label` as field_label","`tabDocField`.`name` as field_name"]""",
				"filters": "[]",
				"order_by": "_aggregate_column desc",
				"start": 0,
				"page_length": 20,
				"view": "Report",
				"with_comment_count": 0,
				"group_by": "field_label, field_name",
				"aggregate_on_field": "columns",
				"aggregate_on_doctype": "DocField",
				"aggregate_function": "sum",
			}
		)

		response = execute_cmd("frappe.desk.reportview.get")
		self.assertListEqual(response["keys"], ["field_label", "field_name", "_aggregate_column"])

	def test_reportview_get_permlevel_system_users(self):
		with setup_patched_blog_post(), setup_test_user(set_user=True):
			frappe.local.request = frappe._dict()
			frappe.local.request.method = "POST"
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Test Blog Post",
					"fields": ["published", "title", "`tabTest Child`.`test_field`"],
				}
			)

			# even if * is passed, fields which are not accessible should be filtered out
			response = execute_cmd("frappe.desk.reportview.get")
			self.assertListEqual(response["keys"], ["title"])
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Test Blog Post",
					"fields": ["*"],
				}
			)

			response = execute_cmd("frappe.desk.reportview.get")
			self.assertNotIn("published", response["keys"])

			data = frappe.get_list("Test Blog Post", "published")
			self.assertTrue(len(data) > 0)
			self.assertTrue(all("name" in row for row in data))
			self.assertTrue(all("published" not in row for row in data))

	def test_reportview_get_admin(self):
		# Admin should be able to see access all fields
		with setup_patched_blog_post():
			frappe.local.request = frappe._dict()
			frappe.local.request.method = "POST"
			frappe.local.form_dict = frappe._dict(
				{
					"doctype": "Test Blog Post",
					"fields": ["published", "title", "`tabTest Child`.`test_field`"],
				}
			)
			response = execute_cmd("frappe.desk.reportview.get")
			self.assertListEqual(response["keys"], ["published", "title", "test_field"])

	def test_db_filter_not_set(self):
		"""
		Test if the 'not set' filter always translates correctly with/without qb under the hood.
		"""
		frappe.get_doc({"doctype": "ToDo", "description": "filter test"}).insert()
		frappe.get_doc({"doctype": "ToDo", "description": "filter test", "reference_name": ""}).insert()

		# `get_all` does not use QueryBuilder while `count` does. Both should return the same result.
		# `not set` must consider empty strings and NULL values both.
		self.assertEqual(
			len(frappe.get_all("ToDo", filters={"reference_name": ["is", "not set"]})),
			frappe.db.count("ToDo", {"reference_name": ["is", "not set"]}),
		)


def add_child_table_to_blog_post():
	child_table = frappe.get_doc(
		{
			"doctype": "DocType",
			"istable": 1,
			"custom": 1,
			"name": "Test Child",
			"module": "Custom",
			"autoname": "Prompt",
			"fields": [{"fieldname": "test_field", "fieldtype": "Data", "permlevel": 1}],
		}
	)

	child_table.insert(ignore_permissions=True, ignore_if_duplicate=True)
	clear_custom_fields("Test Blog Post")
	add_custom_field("Test Blog Post", "child_table", "Table", child_table.name)


def create_event(subject="_Test Event", starts_on=None):
	"""create a test event"""

	from frappe.utils import get_datetime

	return frappe.get_doc(
		{
			"doctype": "Event",
			"subject": subject,
			"event_type": "Public",
			"starts_on": get_datetime(starts_on),
		}
	).insert(ignore_permissions=True)


def create_nested_doctype():
	if frappe.db.exists("DocType", "Nested DocType"):
		return

	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": "Nested DocType",
			"module": "Custom",
			"is_tree": 1,
			"custom": 1,
			"autoname": "Prompt",
			"fields": [{"label": "Description", "fieldname": "description"}],
			"permissions": [{"role": "Blogger"}],
		}
	).insert()


def create_nested_doctype_records():
	"""
	Create a structure like:
	- Root
	        - Level 1 A
	                - Level 2 A
	                        - Level 3 A
	        - Level 1 B
	                - Level 2 B
	"""
	records = [
		{"name": "Root", "is_group": 1},
		{"name": "Level 1 A", "parent_nested_doctype": "Root", "is_group": 1},
		{"name": "Level 2 A", "parent_nested_doctype": "Level 1 A", "is_group": 1},
		{"name": "Level 3 A", "parent_nested_doctype": "Level 2 A"},
		{"name": "Level 1 B", "parent_nested_doctype": "Root", "is_group": 1},
		{"name": "Level 2 B", "parent_nested_doctype": "Level 1 B"},
	]

	for r in records:
		d = frappe.new_doc("Nested DocType")
		d.update(r)
		d.insert(ignore_permissions=True, ignore_if_duplicate=True)
