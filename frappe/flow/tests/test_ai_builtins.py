# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow.tools.builtins import (
	BUILTIN_TOOLS,
	create,
	delete,
	describe,
	execute,
	find_doctypes,
	read,
	sync_builtin_tools,
	update,
)


class TestFindDoctypes(IntegrationTestCase):
	def test_search_matches_by_keyword(self):
		names = {r["name"] for r in find_doctypes(search="ToDo")}
		self.assertIn("ToDo", names)

	def test_filters_by_module(self):
		rows = find_doctypes(module="Core", limit=200)
		self.assertTrue(rows)
		self.assertTrue(all(r["module"] == "Core" for r in rows))

	def test_excludes_child_tables(self):
		names = {r["name"] for r in find_doctypes(search="Role", limit=200)}
		self.assertIn("Role", names)
		self.assertNotIn("Has Role", names)  # a child table that also matches "Role"

	def test_includes_single_doctypes(self):
		names = {r["name"] for r in find_doctypes(search="System Settings", limit=200)}
		self.assertIn("System Settings", names)  # a single DocType

	def test_respects_read_permission(self):
		frappe.set_user("Guest")
		try:
			names = {r["name"] for r in find_doctypes(search="User", limit=200)}
			self.assertNotIn("User", names)
		finally:
			frappe.set_user("Administrator")


class TestDescribe(IntegrationTestCase):
	def test_returns_fields_and_permissions(self):
		result = describe(doctype="ToDo")

		self.assertEqual(result["doctype"], "ToDo")
		fieldnames = {f["fieldname"] for f in result["fields"]}
		self.assertIn("description", fieldnames)
		self.assertEqual(set(result["permissions"]), {"read", "write", "create", "delete"})

	def test_excludes_layout_fields(self):
		result = describe(doctype="ToDo")
		types = {f["type"] for f in result["fields"]}
		self.assertNotIn("Section Break", types)
		self.assertNotIn("Column Break", types)

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(PermissionError):
				describe(doctype="User")
		finally:
			frappe.set_user("Administrator")


class TestRead(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_reads_matching_records(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "ai builtin read probe"}).insert()

		rows = read(doctype="ToDo", filters={"description": "ai builtin read probe"})

		self.assertEqual([r["name"] for r in rows], [todo.name])

	def test_limit_is_capped(self):
		rows = read(doctype="DocType", limit=10_000)
		self.assertLessEqual(len(rows), 200)

	def test_returns_requested_fields(self):
		frappe.get_doc({"doctype": "ToDo", "description": "fields probe"}).insert()
		rows = read(doctype="ToDo", filters={"description": "fields probe"}, fields=["name", "description"])
		self.assertEqual(rows[0]["description"], "fields probe")


class TestExecute(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_returns_result_variable(self):
		self.assertEqual(execute(code="result = 1 + 1", description="Add two numbers"), 2)

	def test_no_result_returns_none(self):
		self.assertIsNone(execute(code="x = 5", description="Set a variable"))

	def test_can_read_via_frappe(self):
		count = execute(code="result = frappe.db.count('DocType')", description="Count doctypes")
		self.assertIsInstance(count, int)

	def test_imports_are_blocked(self):
		with self.assertRaises(Exception):
			execute(code="import os\nresult = os.getcwd()", description="Get working directory")


class TestCreate(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(create.requires_confirmation)

	def test_creates_doc_with_values(self):
		result = create(doctype="ToDo", records=[{"description": "ai create probe"}])

		self.assertEqual(result["doctype"], "ToDo")
		self.assertEqual(len(result["created"]), 1)
		name = result["created"][0]
		self.assertTrue(frappe.db.exists("ToDo", name))
		self.assertEqual(frappe.db.get_value("ToDo", name, "description"), "ai create probe")

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			create(doctype="User", records=[{"email": "x@example.com"}])

	def test_missing_required_field_reported_as_failure(self):
		# ToDo.description is mandatory; the row fails validation and is reported, not raised.
		result = create(doctype="ToDo", records=[{}])

		self.assertEqual(result["created"], [])
		self.assertEqual(len(result["failures"]), 1)
		self.assertEqual(result["failures"][0]["row"], 0)


class TestUpdate(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai update probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(update.requires_confirmation)

	def test_modifies_doc_fields(self):
		result = update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"})

		self.assertEqual(result["updated"], [self.todo.name])
		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "status"), "Closed")

	def test_invalid_value_reported_as_failure(self):
		# Status is a Select field with a fixed set; an invalid value fails that row.
		result = update(doctype="ToDo", names=[self.todo.name], values={"status": "Not A Real Status"})

		self.assertEqual(result["updated"], [])
		self.assertEqual(len(result["failures"]), 1)

	def test_missing_record_reported_as_failure(self):
		result = update(doctype="ToDo", names=["does-not-exist"], values={"status": "Closed"})

		self.assertEqual(result["updated"], [])
		self.assertEqual(result["failures"][0]["name"], "does-not-exist")

	def test_permission_denied_reported_as_failure(self):
		frappe.set_user("Guest")
		result = update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"})

		self.assertEqual(result["updated"], [])
		self.assertEqual(len(result["failures"]), 1)


class TestDelete(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai delete probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(delete.requires_confirmation)

	def test_removes_doc(self):
		result = delete(doctype="ToDo", names=[self.todo.name])

		self.assertEqual(result["deleted"], [self.todo.name])
		self.assertFalse(frappe.db.exists("ToDo", self.todo.name))

	def test_missing_record_reported_as_failure(self):
		result = delete(doctype="ToDo", names=["does-not-exist"])

		self.assertEqual(result["deleted"], [])
		self.assertEqual(result["failures"][0]["name"], "does-not-exist")

	def test_permission_denied_reported_as_failure(self):
		frappe.set_user("Guest")
		result = delete(doctype="ToDo", names=[self.todo.name])

		self.assertEqual(result["deleted"], [])
		self.assertEqual(len(result["failures"]), 1)


class TestSyncBuiltinTools(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_creates_rows_for_all_builtins(self):
		sync_builtin_tools()
		for builtin in BUILTIN_TOOLS:
			self.assertTrue(frappe.db.exists("Flow Tool", builtin.name))

	def test_resolves_back_to_runtime_tool(self):
		sync_builtin_tools()
		doc = frappe.get_doc("Flow Tool", "describe")
		runtime = doc.to_tool()
		self.assertEqual(runtime.name, "describe")
		self.assertIn("doctype", runtime.parameters["properties"])

	def test_is_idempotent(self):
		sync_builtin_tools()
		sync_builtin_tools()
		count = frappe.db.count("Flow Tool", {"slug": "read"})
		self.assertEqual(count, 1)
